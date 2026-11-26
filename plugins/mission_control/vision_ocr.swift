// Local macOS Vision OCR helper. One JSON object per image; no network access.
import Foundation
import Vision

struct FrameResult: Encodable {
    let path: String
    let text: String
    let confidence: Float
    let error: String?
}

for path in CommandLine.arguments.dropFirst() {
    do {
        let url = URL(fileURLWithPath: path)
        let request = VNRecognizeTextRequest()
        request.recognitionLevel = .accurate
        request.usesLanguageCorrection = false
        request.recognitionLanguages = ["pt-BR", "en-US"]
        try VNImageRequestHandler(url: url).perform([request])
        let observations = request.results ?? []
        let candidates = observations.compactMap { $0.topCandidates(1).first }
        let text = candidates.map(\.string).joined(separator: "\n")
        let confidence = candidates.isEmpty ? 0 : candidates.map(\.confidence).reduce(0, +) / Float(candidates.count)
        let result = FrameResult(path: path, text: text, confidence: confidence, error: nil)
        let data = try JSONEncoder().encode(result)
        print(String(data: data, encoding: .utf8) ?? "{}")
    } catch {
        let result = FrameResult(path: path, text: "", confidence: 0, error: String(describing: error))
        if let data = try? JSONEncoder().encode(result) {
            print(String(data: data, encoding: .utf8) ?? "{}")
        }
    }
}
