// Escucha el sonido del Mac y escribe su espectro: 21 bandas (de graves a agudos), cada una
// de 0 a 255, en una línea de texto unas 30 veces por segundo. ak820.py lo lee para el modo
// música del teclado.
//
// Usa los "taps" de Core Audio (macOS 14.2+): un tap privado de todo el audio del sistema
// metido en un dispositivo agregado privado. El permiso que pide macOS es "Grabación de
// audio del sistema" (solo audio, no la pantalla). Sin permiso, el tap da silencio.
//
// Se para al cerrarse su entrada estándar (cuando termina quien lo lanzó).
//
//     swiftc -O -swift-version 5 musica/espectro.swift -o musica/espectro

import Accelerate
import CoreAudio
import Foundation

let BANDAS = 21
let TAM_FFT = 2048
let LOG2N = vDSP_Length(11)
let FRECUENCIA_MIN: Float = 45
let FRECUENCIA_MAX: Float = 14000
let MARGEN_DB: Float = 48         // lo que cabe entre una barra apagada y una llena

func fallar(_ mensaje: String) -> Never {
    FileHandle.standardError.write((mensaje + "\n").data(using: .utf8)!)
    exit(1)
}

func propiedad<T>(_ objeto: AudioObjectID, _ selector: AudioObjectPropertySelector, _ valor: inout T) -> OSStatus {
    var direccion = AudioObjectPropertyAddress(mSelector: selector, mScope: kAudioObjectPropertyScopeGlobal,
                                               mElement: kAudioObjectPropertyElementMain)
    var tamano = UInt32(MemoryLayout<T>.size)
    return AudioObjectGetPropertyData(objeto, &direccion, 0, nil, &tamano, &valor)
}

// --- Muestras: el bloque de audio deja aquí la mezcla en mono; el temporizador la lee. ----------
final class Anillo {
    private var datos = [Float](repeating: 0, count: TAM_FFT * 4)
    private var escritura = 0
    private let candado = NSLock()

    func anadir(_ muestras: UnsafeBufferPointer<Float>) {
        candado.lock()
        for m in muestras {
            datos[escritura] = m
            escritura = (escritura + 1) % datos.count
        }
        candado.unlock()
    }

    func ultimas(_ n: Int) -> [Float] {
        candado.lock()
        defer { candado.unlock() }
        return (0..<n).map { datos[(escritura - n + $0 + datos.count) % datos.count] }
    }
}
let anillo = Anillo()

// --- El tap y el dispositivo agregado ---------------------------------------------------------
let descripcion = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
descripcion.uuid = UUID()
descripcion.muteBehavior = .unmuted
descripcion.isPrivate = true
var tap = AudioObjectID(kAudioObjectUnknown)
guard AudioHardwareCreateProcessTap(descripcion, &tap) == noErr else { fallar("No se puede crear el tap de audio (¿macOS 14.2 o posterior?).") }

var salida = AudioObjectID(kAudioObjectUnknown)
guard propiedad(AudioObjectID(kAudioObjectSystemObject), kAudioHardwarePropertyDefaultSystemOutputDevice, &salida) == noErr
else { fallar("No encuentro la salida de audio del Mac.") }
var uidSalida: CFString = "" as CFString
guard propiedad(salida, kAudioDevicePropertyDeviceUID, &uidSalida) == noErr else { fallar("Salida de audio sin UID.") }

let agregado: [String: Any] = [
    kAudioAggregateDeviceNameKey: "AK820 música",
    kAudioAggregateDeviceUIDKey: UUID().uuidString,
    kAudioAggregateDeviceMainSubDeviceKey: uidSalida as String,
    kAudioAggregateDeviceIsPrivateKey: true,
    kAudioAggregateDeviceIsStackedKey: false,
    kAudioAggregateDeviceTapAutoStartKey: true,
    kAudioAggregateDeviceSubDeviceListKey: [[kAudioSubDeviceUIDKey: uidSalida as String]],
    kAudioAggregateDeviceTapListKey: [[kAudioSubTapDriftCompensationKey: true,
                                       kAudioSubTapUIDKey: descripcion.uuid.uuidString]],
]
var dispositivo = AudioObjectID(kAudioObjectUnknown)
guard AudioHardwareCreateAggregateDevice(agregado as CFDictionary, &dispositivo) == noErr
else { fallar("No se puede crear el dispositivo de audio agregado.") }

var formato = AudioStreamBasicDescription()
guard propiedad(tap, kAudioTapPropertyFormat, &formato) == noErr else { fallar("No se puede leer el formato del tap.") }
let canales = Int(max(formato.mChannelsPerFrame, 1))
let frecuencia = Float(formato.mSampleRate > 0 ? formato.mSampleRate : 48000)
let entrelazado = formato.mFormatFlags & kAudioFormatFlagIsNonInterleaved == 0

var proceso: AudioDeviceIOProcID?
let cola = DispatchQueue(label: "ak820.audio", qos: .userInteractive)
let estado = AudioDeviceCreateIOProcIDWithBlock(&proceso, dispositivo, cola) { _, entrada, _, _, _ in
    let lista = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: entrada))
    guard let primero = lista.first, let base = primero.mData else { return }
    if entrelazado {
        let total = Int(primero.mDataByteSize) / MemoryLayout<Float>.size
        let muestras = base.assumingMemoryBound(to: Float.self)
        var mono = [Float](repeating: 0, count: total / canales)
        for i in 0..<mono.count {
            var suma: Float = 0
            for c in 0..<canales { suma += muestras[i * canales + c] }
            mono[i] = suma / Float(canales)
        }
        mono.withUnsafeBufferPointer { anillo.anadir($0) }
    } else {
        let total = Int(primero.mDataByteSize) / MemoryLayout<Float>.size
        var mono = [Float](repeating: 0, count: total)
        for bufer in lista {
            guard let datos = bufer.mData?.assumingMemoryBound(to: Float.self) else { continue }
            for i in 0..<total { mono[i] += datos[i] / Float(lista.count) }
        }
        mono.withUnsafeBufferPointer { anillo.anadir($0) }
    }
}
guard estado == noErr, let proceso = proceso else { fallar("No se puede leer el audio.") }
guard AudioDeviceStart(dispositivo, proceso) == noErr else { fallar("No se puede empezar a escuchar.") }

func terminar() -> Never {
    AudioDeviceStop(dispositivo, proceso)
    AudioDeviceDestroyIOProcID(dispositivo, proceso)
    AudioHardwareDestroyAggregateDevice(dispositivo)
    AudioHardwareDestroyProcessTap(tap)
    exit(0)
}

// Si se cierra la entrada (el programa que nos lanzó ha terminado), se para.
Thread.detachNewThread {
    while FileHandle.standardInput.availableData.count > 0 {}
    terminar()
}
signal(SIGTERM) { _ in exit(0) }
signal(SIGINT) { _ in exit(0) }

// --- Espectro: FFT con ventana de Hann, 21 bandas logarítmicas, en dB con ganancia automática --
let fft = vDSP_create_fftsetup(LOG2N, FFTRadix(kFFTRadix2))!
var ventana = [Float](repeating: 0, count: TAM_FFT)
vDSP_hann_window(&ventana, vDSP_Length(TAM_FFT), Int32(vDSP_HANN_NORM))
let anchoBin = frecuencia / Float(TAM_FFT)
let bordes: [Int] = (0...BANDAS).map { i in
    let f = FRECUENCIA_MIN * pow(FRECUENCIA_MAX / FRECUENCIA_MIN, Float(i) / Float(BANDAS))
    return max(1, Int(f / anchoBin))
}
var picoDB: Float = -40
var suavizado = [Float](repeating: 0, count: BANDAS)

let temporizador = DispatchSource.makeTimerSource(queue: .main)
temporizador.schedule(deadline: .now(), repeating: .milliseconds(33))
temporizador.setEventHandler {
    var muestras = anillo.ultimas(TAM_FFT)
    vDSP_vmul(muestras, 1, ventana, 1, &muestras, 1, vDSP_Length(TAM_FFT))
    var real = [Float](repeating: 0, count: TAM_FFT / 2)
    var imaginaria = [Float](repeating: 0, count: TAM_FFT / 2)
    var magnitudes = [Float](repeating: 0, count: TAM_FFT / 2)
    real.withUnsafeMutableBufferPointer { re in
        imaginaria.withUnsafeMutableBufferPointer { im in
            var complejo = DSPSplitComplex(realp: re.baseAddress!, imagp: im.baseAddress!)
            muestras.withUnsafeBytes {
                vDSP_ctoz($0.bindMemory(to: DSPComplex.self).baseAddress!, 2, &complejo, 1, vDSP_Length(TAM_FFT / 2))
            }
            vDSP_fft_zrip(fft, &complejo, 1, LOG2N, FFTDirection(FFT_FORWARD))
            vDSP_zvabs(&complejo, 1, &magnitudes, 1, vDSP_Length(TAM_FFT / 2))
        }
    }
    var niveles = [Float](repeating: 0, count: BANDAS)
    var maximo: Float = -200
    for b in 0..<BANDAS {
        let desde = min(bordes[b], TAM_FFT / 2 - 1)
        let hasta = min(max(bordes[b + 1], desde + 1), TAM_FFT / 2)
        let pico = magnitudes[desde..<hasta].max() ?? 0
        niveles[b] = 20 * log10(pico + 1e-9)
        maximo = max(maximo, niveles[b])
    }
    // Ganancia automática: el pico sube al momento y baja despacio (unos 10 dB por segundo).
    picoDB = max(maximo, picoDB - 0.33)
    var linea = ""
    for b in 0..<BANDAS {
        let valor = max(0, min(1, (niveles[b] - (picoDB - MARGEN_DB)) / MARGEN_DB))
        suavizado[b] = max(valor, suavizado[b] * 0.82)      // sube rápido y cae poco a poco
        linea += (b == 0 ? "" : " ") + String(Int(suavizado[b] * 255))
    }
    if maximo < -100 { linea = Array(repeating: "0", count: BANDAS).joined(separator: " ") }   // silencio
    print(linea)
    fflush(stdout)
}
temporizador.resume()
dispatchMain()
