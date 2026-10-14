import Foundation
import CoreImage
import ImageIO
import UniformTypeIdentifiers
let src=CIImage(contentsOf:URL(fileURLWithPath:CommandLine.arguments[1]))!
let mask=src.applyingFilter("CIMaximumComponent").applyingFilter("CIColorThreshold",parameters:["inputThreshold":0.85])
let cg=CIContext(options:[.useSoftwareRenderer:true]).createCGImage(mask,from:src.extent)!
let dst=CGImageDestinationCreateWithURL(URL(fileURLWithPath:CommandLine.arguments[2]) as CFURL,UTType.png.identifier as CFString,1,nil)!
CGImageDestinationAddImage(dst,cg,nil)
if !CGImageDestinationFinalize(dst){exit(1)}
