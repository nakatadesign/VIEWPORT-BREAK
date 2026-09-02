import Foundation
import CoreGraphics
let pid = Int32(CommandLine.arguments[1])!
guard let list = CGWindowListCopyWindowInfo([.optionAll], kCGNullWindowID) as? [[String: Any]] else {
    print("window list unavailable"); exit(2)
}
var n = 0
for w in list {
    guard let owner = w[kCGWindowOwnerPID as String] as? Int32, owner == pid else { continue }
    n += 1
    let layer = w[kCGWindowLayer as String] as? Int ?? -999
    let onscreen = w[kCGWindowIsOnscreen as String] as? Bool ?? false
    let alpha = w[kCGWindowAlpha as String] as? Double ?? -1
    let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
    let name = w[kCGWindowName as String] as? String ?? "(name unavailable)"
    print("window#\(n) layer=\(layer) onscreen=\(onscreen) alpha=\(alpha) bounds=\(b) name=\(name)")
}
print("total_windows_for_pid=\(n)")
