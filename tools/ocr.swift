import Foundation
import Vision
import ImageIO

guard CommandLine.arguments.count == 2 else { fatalError("usage: ocr IMAGE") }
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let source = CGImageSourceCreateWithURL(url as CFURL, nil)!
let image = CGImageSourceCreateImageAtIndex(source, 0, nil)!
let request = VNRecognizeTextRequest()
let languages = ProcessInfo.processInfo.environment["NSP_OCR_LANGUAGES"]?
    .split(separator: ",").map(String.init) ?? ["zh-Hans", "en-US"]
request.recognitionLevel = languages == ["en-US"] ? .fast : .accurate
request.revision = VNRecognizeTextRequestRevision2
request.recognitionLanguages = languages
request.usesLanguageCorrection = false
try VNImageRequestHandler(cgImage: image).perform([request])
let rows: [[String: Any]] = (request.results ?? []).compactMap { item in
    guard let text = item.topCandidates(1).first else { return nil }
    let r = item.boundingBox
    return ["text": text.string, "confidence": text.confidence,
            "bounds": [r.minX * Double(image.width), (1-r.maxY) * Double(image.height),
                       r.width * Double(image.width), r.height * Double(image.height)]]
}
let result: [String: Any] = ["source": "vision-ocr", "width": image.width, "height": image.height, "elements": rows]
let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
FileHandle.standardOutput.write(data)
