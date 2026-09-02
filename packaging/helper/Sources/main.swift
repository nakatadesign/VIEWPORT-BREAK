// VIEWPORT BREAK — native messaging host / インストーラ / CLI を兼ねる単一バイナリ。
//
// なぜ Swift のコンパイル済みバイナリなのか:
//   同等の処理は extension/host/viewport_deck_host.py が既に Python でやっている。
//   だが /usr/bin/python3 は Command Line Tools 同梱の実体を libxcselect 経由で
//   呼ぶ shim であり、CLT が入っていない Mac では「コマンドラインデベロッパツールを
//   インストールしますか」ダイアログが出るだけで実行できない
//   （実測: docs/DMG_DISTRIBUTION_2026-08-30.md §2.1）。
//   DMG を買った人の Mac に CLT がある保証は無いので、配布物は Python に依存できない。
//
//   もう一つの理由は TCC（オートメーション権限）の帰属先。shebang スクリプトは
//   /usr/bin/python3 として実行されるため、許可のダイアログにも許可リストにも
//   「python3」と出る。.app に入れた実バイナリなら、この製品名で帰属する。
//
// 動作モードは argv で決まる:
//   chrome-extension://... で始まる  → native messaging host（Chrome が起動する形）
//   --install / --uninstall / --doctor / 幅指定など → CLI
//   引数なし・-psn_*（Finder からの起動）        → GUI セットアップ
//
// 幅の下限を貫通する仕組みは Python 版と同じ。AppleScript の `set bounds` だけが
// Widget::SetBounds() を通らないため、500 DIP のクランプに掛からない。
// 詳細は docs/WINDOW_FLOOR_2026-08-30.md。

import Foundation
import AppKit

// MARK: - 定数

let HOST_VERSION  = "2.0.1"
let HOST_NAME     = "com.nanago.viewport_deck"   // 拡張の core.js と一致させる。改名しない
let EXT_ID        = "ejlimgikbnaihoigbcmelaadniiminfj"
let TARGET_APP    = "Google Chrome"
let ENGINE        = "applescript:set-bounds"
let MIN_WIDTH     = 1
let MAX_WIDTH     = 8000
let RESTORE_WIDTH = 1280
let PRODUCT_NAME  = "VIEWPORT BREAK"
let NOT_RUNNING   = "__VB_NOT_RUNNING__"

struct HostError: Error {
    let message: String
    init(_ m: String) { message = m }
}

let HOME = NSHomeDirectory()
// E2E は実ユーザーの Application Support を触らず、一時ディレクトリへ隔離する。
// 通常起動ではこの環境変数は存在しないため、従来どおりユーザーの Library 配下になる。
let APP_SUPPORT: String = {
    if let p = ProcessInfo.processInfo.environment["VIEWPORT_BREAK_TEST_APP_SUPPORT"], !p.isEmpty {
        return URL(fileURLWithPath: p).standardizedFileURL.path
    }
    return "\(HOME)/Library/Application Support"
}()
let APP_DATA_DIR = "\(APP_SUPPORT)/\(PRODUCT_NAME)"

/// 拡張の実体を置く場所。.app の中ではなくここに置くのは、
///  - Chrome の「パッケージ化されていない拡張機能を読み込む」でユーザーが辿り着きやすい
///  - .app を差し替えても拡張のパスが変わらない
///  - .app 内のファイルに付く quarantine 属性を持ち込まない
/// の 3 点による。
let EXT_INSTALL_DIR = "\(APP_DATA_DIR)/extension"

// MARK: - AppleScript

/// NSAppleScript で in-process 実行する。osascript を spawn しないのは、
/// spawn すると TCC の許可対象が osascript になり、この .app に帰属しなくなるため。
func runAppleScript(_ source: String) throws -> String {
    guard let script = NSAppleScript(source: source) else {
        throw HostError("AppleScript をコンパイルできなかった")
    }
    var errInfo: NSDictionary?
    let result = script.executeAndReturnError(&errInfo)
    if let e = errInfo {
        let num = (e["NSAppleScriptErrorNumber"] as? Int) ?? 0
        let msg = (e["NSAppleScriptErrorMessage"] as? String) ?? "\(e)"
        // -1743 = errAEEventNotPermitted（オートメーション権限が無い / 拒否された）
        if num == -1743 {
            throw HostError("オートメーション権限がない。システム設定 → プライバシーとセキュリティ → "
                + "オートメーション で \(PRODUCT_NAME) から \(TARGET_APP) への許可を有効にする。(-1743)")
        }
        // -600 = procNotFound
        if num == -600 {
            throw HostError("\(TARGET_APP) が起動していない")
        }
        throw HostError("AppleScript 失敗 (\(num)): \(msg)")
    }
    return result.stringValue ?? ""
}

struct Win {
    var id: Int, left: Int, top: Int, width: Int, height: Int
    var dict: [String: Any] {
        ["id": id, "left": left, "top": top, "width": width, "height": height]
    }
}

/// Chrome の全ウィンドウを返す。
/// `is running` の guard を必ず通す。素の tell は Chrome が終了していると起動してしまう。
func listWindows() throws -> [Win] {
    let src = """
    if application "\(TARGET_APP)" is running then
      tell application "\(TARGET_APP)"
        set out to ""
        repeat with w in windows
          set b to bounds of w
          set out to out & (id of w as text) & "," & (item 1 of b as text) & "," & (item 2 of b as text) & "," & (item 3 of b as text) & "," & (item 4 of b as text) & linefeed
        end repeat
        return out
      end tell
    else
      return "\(NOT_RUNNING)"
    end if
    """
    let out = try runAppleScript(src)
    if out.trimmingCharacters(in: .whitespacesAndNewlines) == NOT_RUNNING {
        throw HostError("\(TARGET_APP) が起動していない")
    }
    var wins: [Win] = []
    for rawLine in out.split(whereSeparator: { $0 == "\n" || $0 == "\r" }) {
        let parts = rawLine.trimmingCharacters(in: .whitespaces).split(separator: ",")
        guard parts.count == 5 else { continue }
        let v = parts.compactMap { Int($0.trimmingCharacters(in: .whitespaces)) }
        guard v.count == 5 else { continue }
        wins.append(Win(id: v[0], left: v[1], top: v[2], width: v[3] - v[1], height: v[4] - v[2]))
    }
    return wins
}

func setBoundsOf(_ id: Int, l: Int, t: Int, r: Int, b: Int) throws {
    _ = try runAppleScript(
        "if application \"\(TARGET_APP)\" is running then "
        + "tell application \"\(TARGET_APP)\" to set bounds of window id \(id) to {\(l), \(t), \(r), \(b)}")
}

/// 拡張が送ってきた chrome.windows の bounds に対応する AppleScript ウィンドウを選ぶ。
/// 両者の座標系・単位は一致する（実測済み）。Python 版と同じ 4 段階で絞る。
func pickWindow(_ wins: [Win], _ match: [String: Any]?) throws -> Win {
    guard !wins.isEmpty else { throw HostError("\(TARGET_APP) のウィンドウが 1 つも無い") }
    guard let m = match else { return wins[0] }
    func g(_ k: String) -> Int? {
        if let i = m[k] as? Int { return i }
        if let d = m[k] as? Double { return Int(d) }
        return nil
    }
    let ml = g("left"), mt = g("top"), mw = g("width"), mh = g("height")

    // 1. 完全一致
    if let ml, let mt, let mw, let mh,
       let w = wins.first(where: { $0.left == ml && $0.top == mt && $0.width == mw && $0.height == mh }) {
        return w
    }
    // 2. 左上一致（直前に高さだけ変わっている等）
    if let ml, let mt, let w = wins.first(where: { $0.left == ml && $0.top == mt }) { return w }
    // 3. 1 枚しか無いなら曖昧さは無い
    if wins.count == 1 { return wins[0] }
    // 4. 左上への距離が最も近いもの。遠すぎるなら諦める
    if let ml, let mt {
        let best = wins.min(by: { abs($0.left - ml) + abs($0.top - mt) < abs($1.left - ml) + abs($1.top - mt) })!
        if abs(best.left - ml) + abs(best.top - mt) <= 40 { return best }
    }
    throw HostError("対象ウィンドウを特定できなかった（候補 \(wins.count) 枚）")
}

func checkWidth(_ w: Int) throws {
    guard w >= MIN_WIDTH && w <= MAX_WIDTH else {
        throw HostError("幅は \(MIN_WIDTH)〜\(MAX_WIDTH) の範囲で指定する: \(w)")
    }
}

/// 幅を width にする。高さ未指定なら現在の高さを保つ。
/// 「設定した」ではなく「実際にそうなった」を読み返して返す。
func setWidth(_ width: Int, height: Int?, match: [String: Any]?) throws -> Win {
    try checkWidth(width)
    let win = try pickWindow(try listWindows(), match)
    let h = height ?? win.height
    try setBoundsOf(win.id, l: win.left, t: win.top, r: win.left + width, b: win.top + h)
    guard let after = (try listWindows()).first(where: { $0.id == win.id }) else {
        throw HostError("設定後にウィンドウを読み返せなかった（id=\(win.id)）")
    }
    return after
}

/// 狭くしすぎて popup も拡張アイコンも触れなくなったときの復帰口。
/// 「現在のウィンドウ」ではなく **一番狭いウィンドウ** を選ぶ。この経路を打つ時点で
/// Chrome は前面ですらなく、対象を名指しできる情報がそれしか無いため。
func restoreWidth(_ width: Int?) throws -> (before: Win, after: Win) {
    let w = width ?? RESTORE_WIDTH
    try checkWidth(w)
    let wins = try listWindows()
    guard let target = wins.min(by: { $0.width < $1.width }) else {
        throw HostError("\(TARGET_APP) のウィンドウが 1 つも無い")
    }
    try setBoundsOf(target.id, l: target.left, t: target.top,
                    r: target.left + w, b: target.top + target.height)
    guard let after = (try listWindows()).first(where: { $0.id == target.id }) else {
        throw HostError("設定後にウィンドウを読み返せなかった（id=\(target.id)）")
    }
    return (target, after)
}

// MARK: - リクエスト処理（native messaging と CLI で共有）

func handle(_ req: [String: Any]) throws -> [String: Any] {
    let cmd = (req["cmd"] as? String) ?? ""
    let match = req["match"] as? [String: Any]
    switch cmd {
    case "ping":
        return ["ok": true, "host_version": HOST_VERSION, "engine": ENGINE,
                "impl": "swift", "path": selfExecutablePath()]
    case "set":
        guard let wv = req["width"] as? NSNumber else { throw HostError("width が無い") }
        let h = (req["height"] as? NSNumber).map { $0.intValue }
        let b = try setWidth(wv.intValue, height: h, match: match)
        return ["ok": true, "bounds": b.dict, "engine": ENGINE]
    case "get":
        return ["ok": true, "bounds": try pickWindow(try listWindows(), match).dict, "engine": ENGINE]
    case "list":
        return ["ok": true, "windows": try listWindows().map { $0.dict }, "engine": ENGINE]
    case "restore":
        let r = try restoreWidth((req["width"] as? NSNumber).map { $0.intValue })
        return ["ok": true, "bounds": r.after.dict, "before": r.before.dict, "engine": ENGINE]
    default:
        throw HostError("未知のコマンド: \(cmd)")
    }
}

// MARK: - native messaging（stdin/stdout・4 バイト長プレフィクス）

func readExact(_ n: Int) -> Data? {
    var data = Data()
    var buf = [UInt8](repeating: 0, count: 65536)
    while data.count < n {
        let want = min(n - data.count, buf.count)
        let got = buf.withUnsafeMutableBytes { read(0, $0.baseAddress, want) }
        if got <= 0 { return nil }
        data.append(contentsOf: buf[0..<got])
    }
    return data
}

func writeAll(_ data: Data) {
    data.withUnsafeBytes { (p: UnsafeRawBufferPointer) in
        guard let base = p.baseAddress else { return }
        var off = 0
        while off < data.count {
            let n = write(1, base.advanced(by: off), data.count - off)
            if n <= 0 { return }
            off += n
        }
    }
}

func nmWrite(_ obj: [String: Any]) {
    guard let body = try? JSONSerialization.data(withJSONObject: obj) else { return }
    var len = UInt32(body.count).littleEndian
    writeAll(Data(bytes: &len, count: 4))
    writeAll(body)
}

func serve() {
    while true {
        guard let head = readExact(4) else { return }   // Chrome がパイプを閉じた = 正常終了
        let n = head.withUnsafeBytes { $0.loadUnaligned(as: UInt32.self) }
        let len = Int(UInt32(littleEndian: n))
        if len <= 0 || len > 64 * 1024 * 1024 { return }
        guard let body = readExact(len) else { return }
        do {
            guard let req = try JSONSerialization.jsonObject(with: body) as? [String: Any] else {
                nmWrite(["ok": false, "error": "JSON オブジェクトではない"]); continue
            }
            nmWrite(try handle(req))
        } catch let e as HostError {
            nmWrite(["ok": false, "error": e.message])
        } catch {
            nmWrite(["ok": false, "error": "内部エラー: \(error)"])
        }
    }
}

// MARK: - 自分自身の場所

func selfExecutablePath() -> String {
    if let p = Bundle.main.executablePath { return p }
    return CommandLine.arguments.first.map {
        URL(fileURLWithPath: $0).standardizedFileURL.path
    } ?? "viewport-break"
}

/// .app に入っていれば Contents/Resources、素のバイナリならその隣を返す。
func resourcesDir() -> String {
    let exe = URL(fileURLWithPath: selfExecutablePath())
    let macos = exe.deletingLastPathComponent()                 // Contents/MacOS
    if macos.lastPathComponent == "MacOS" {
        return macos.deletingLastPathComponent().appendingPathComponent("Resources").path
    }
    return macos.path
}

// MARK: - インストーラ

/// native messaging manifest の設置先は Chrome の **user data dir 直下**。
/// 既定プロファイルなら ~/Library/Application Support/Google/Chrome/NativeMessagingHosts。
/// --user-data-dir を付けて起動した Chrome はそちらを見るため、テスト時はここを差し替える。
func defaultBrowserDirs() -> [String] {
    return [
        "\(APP_SUPPORT)/Google/Chrome",
    ]
}

/// 1.0.0 は Chromium 系ブラウザにも同じ manifest を登録していたが、host が操作するのは
/// Google Chrome だけだった。1.0.1 以降は登録しない。アップグレード時の掃除にだけ使う。
func legacyBrowserDirs() -> [String] {
    return [
        "\(APP_SUPPORT)/Google/Chrome Beta",
        "\(APP_SUPPORT)/Google/Chrome Canary",
        "\(APP_SUPPORT)/Chromium",
        "\(APP_SUPPORT)/BraveSoftware/Brave-Browser",
        "\(APP_SUPPORT)/Microsoft Edge",
        "\(APP_SUPPORT)/Vivaldi",
        "\(APP_SUPPORT)/Arc/User Data",
    ]
}

func allKnownBrowserDirs() -> [String] {
    var seen = Set<String>()
    return (defaultBrowserDirs() + legacyBrowserDirs()).filter { seen.insert($0).inserted }
}

@discardableResult
func installHostManifest(into browserDirs: [String], hostPath: String) throws -> [String] {
    let fm = FileManager.default
    var written: [String] = []
    let manifest: [String: Any] = [
        "name": HOST_NAME,
        "description": "\(PRODUCT_NAME) — Chrome ウィンドウ幅を 500px の下限より下へ設定する",
        "path": hostPath,
        "type": "stdio",
        "allowed_origins": ["chrome-extension://\(EXT_ID)/"],
    ]
    // withoutEscapingSlashes: これが無いと path が "\/Applications\/..." になる。
    // JSON としては正しいが、サポートで人が読むファイルなので素直に出す。
    let data = try JSONSerialization.data(
        withJSONObject: manifest,
        options: [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes])
    for dir in browserDirs {
        // そのブラウザのプロファイルが無ければ飛ばす（勝手に作らない）
        var isDir: ObjCBool = false
        guard fm.fileExists(atPath: dir, isDirectory: &isDir), isDir.boolValue else { continue }
        let nmDir = "\(dir)/NativeMessagingHosts"
        try fm.createDirectory(atPath: nmDir, withIntermediateDirectories: true)
        let dest = "\(nmDir)/\(HOST_NAME).json"
        // 既存 manifest を途中で空・半端な JSON にしない。
        try data.write(to: URL(fileURLWithPath: dest), options: .atomic)
        written.append(dest)
    }
    return written
}

struct RemovalResult {
    var removed: [String] = []
    var failures: [[String: String]] = []

    var ok: Bool { failures.isEmpty }

    mutating func removeIfPresent(_ path: String) {
        let fm = FileManager.default
        guard fm.fileExists(atPath: path) else { return }
        do {
            try fm.removeItem(atPath: path)
            removed.append(path)
        } catch {
            failures.append(["path": path, "error": "\(error)"])
        }
    }
}

@discardableResult
func uninstallHostManifest(from browserDirs: [String]) -> RemovalResult {
    var result = RemovalResult()
    for dir in browserDirs {
        let f = "\(dir)/NativeMessagingHosts/\(HOST_NAME).json"
        result.removeIfPresent(f)
    }
    return result
}

func uninstallProduct(from browserDirs: [String]) -> RemovalResult {
    var result = uninstallHostManifest(from: browserDirs)
    result.removeIfPresent(APP_DATA_DIR)
    return result
}

/// quarantine 属性を再帰的に落とす。外部プロセスへ依存せず、対象と失敗を正確に扱うため
/// removexattr(2) を直接呼ぶ。属性が無い ENOATTR だけは成功扱いにする。
func stripQuarantine(_ root: String) throws {
    let fm = FileManager.default
    var paths = [root]
    var failures: [String] = []
    if let e = fm.enumerator(atPath: root) {
        for case let p as String in e { paths.append("\(root)/\(p)") }
    }
    for p in paths {
        if removexattr(p, "com.apple.quarantine", XATTR_NOFOLLOW) != 0, errno != ENOATTR {
            failures.append("\(p): \(String(cString: strerror(errno)))")
        }
    }
    if !failures.isEmpty {
        throw HostError("quarantine 属性を除去できなかった:\n" + failures.joined(separator: "\n"))
    }
}

func hasQuarantine(_ path: String) -> Bool {
    return getxattr(path, "com.apple.quarantine", nil, 0, 0, XATTR_NOFOLLOW) >= 0
}

struct ExtensionInstallResult {
    var path: String
    var warnings: [String]
}

func validateExtension(at path: String) throws {
    let fm = FileManager.default
    let required = [
        "manifest.json", "popup.html", "popup.css", "popup.js", "core.js",
        "background.js", "EXTENSION_ID", "icons/icon16.png", "icons/icon128.png",
    ]
    for relative in required {
        guard fm.fileExists(atPath: "\(path)/\(relative)") else {
            throw HostError("展開前の拡張に必要なファイルが無い: \(relative)")
        }
    }
    let id = try String(contentsOfFile: "\(path)/EXTENSION_ID", encoding: .utf8)
        .trimmingCharacters(in: .whitespacesAndNewlines)
    guard id == EXT_ID else {
        throw HostError("展開前の拡張 ID が一致しない: expected=\(EXT_ID) actual=\(id)")
    }
    let manifestURL = URL(fileURLWithPath: "\(path)/manifest.json")
    let obj = try JSONSerialization.jsonObject(with: Data(contentsOf: manifestURL))
    guard let manifest = obj as? [String: Any], manifest["key"] is String else {
        throw HostError("展開前の manifest.json が不正、または拡張 ID 固定用 key が無い")
    }
}

func exchangePaths(_ a: String, _ b: String) throws {
    let rc = a.withCString { ap in
        b.withCString { bp in
            renameatx_np(AT_FDCWD, ap, AT_FDCWD, bp, UInt32(RENAME_SWAP))
        }
    }
    guard rc == 0 else {
        throw HostError("拡張の新旧切り替えに失敗した: \(String(cString: strerror(errno)))")
    }
}

/// 同梱の拡張を ~/Library/Application Support/VIEWPORT BREAK/extension へ展開する。
/// 新版を一時ディレクトリで検証し、同一ボリューム上の rename swap で切り替える。
/// コピー途中で失敗しても、Chrome が参照している旧 extension は残る。
func installExtension() throws -> ExtensionInstallResult {
    let fm = FileManager.default
    let src = "\(resourcesDir())/extension"
    guard fm.fileExists(atPath: "\(src)/manifest.json") else {
        throw HostError("同梱の拡張が見つからない: \(src)")
    }
    try fm.createDirectory(atPath: APP_DATA_DIR, withIntermediateDirectories: true)

    let staged = "\(APP_DATA_DIR)/.extension.installing-\(UUID().uuidString)"
    var warnings: [String] = []
    do {
        try fm.copyItem(atPath: src, toPath: staged)
        try validateExtension(at: staged)
        try stripQuarantine(staged)
    } catch {
        let primary = error
        if fm.fileExists(atPath: staged) {
            do { try fm.removeItem(atPath: staged) }
            catch {
                throw HostError("拡張の準備に失敗した: \(primary)。一時ファイルも削除できなかった: \(error)")
            }
        }
        throw primary
    }

    if fm.fileExists(atPath: EXT_INSTALL_DIR) {
        try exchangePaths(EXT_INSTALL_DIR, staged)
        // swap 後の staged は旧版。新版は既に正しいパスで利用可能なので、掃除失敗は警告にする。
        do { try fm.removeItem(atPath: staged) }
        catch { warnings.append("旧拡張の一時コピーを削除できなかった: \(staged): \(error)") }
    } else {
        try fm.moveItem(atPath: staged, toPath: EXT_INSTALL_DIR)
    }
    return ExtensionInstallResult(path: EXT_INSTALL_DIR, warnings: warnings)
}

/// macOS は quarantine が付いたままの .app を、ランダムな読み取り専用パスへ
/// コピーして実行することがある（App Translocation）。実測では
/// /private/var/folders/.../AppTranslocation/<uuid>/d/VIEWPORT BREAK.app となった。
///
/// この状態でセットアップを走らせると、native messaging manifest の "path" に
/// **アプリ終了後に消える一時パス** が焼き込まれ、Chrome から host を起動できない
/// インストールが完成してしまう。だから検出したら必ず止める。
/// 購入者が Finder で /Applications へドラッグし、Gatekeeper を許可すればこの状態は解ける。
func translocationProblem() -> String? {
    let p = selfExecutablePath()
    if p.contains("/AppTranslocation/") {
        return "この App は macOS によって一時フォルダへコピーされた状態で実行されています"
            + "（App Translocation）。この状態で設定すると、Chrome から呼び出す先が"
            + "存在しないパスになります。\n\n"
            + "VIEWPORT BREAK.app を Finder でアプリケーションフォルダへドラッグしてから、"
            + "そこにある方をもう一度開いてください。"
    }
    if p.hasPrefix("/Volumes/") {
        return "この App はディスクイメージの中から直接実行されています。\n\n"
            + "VIEWPORT BREAK.app をアプリケーションフォルダへドラッグしてから、"
            + "そちらを開いてください。"
    }
    return nil
}

/// translocated 実行のとき、元々どこに置かれていた .app なのかを返す。
///
/// SecTranslocateCreateOriginalPathForURL は Security.framework に実体があるが、
/// Swift へは import されない（実測: Apple Swift 6.2.4 で "cannot find in scope"）。
/// シンボルは存在するので dlsym で引く。取れなければ nil を返し、呼び出し側は
/// 従来どおり案内アラートへ落ちる。
func originalBundleURL() -> URL? {
    typealias OrigFn = @convention(c) (CFURL, UnsafeMutablePointer<Unmanaged<CFError>?>?) -> Unmanaged<CFURL>?
    guard let h = dlopen("/System/Library/Frameworks/Security.framework/Security", RTLD_LAZY),
          let sym = dlsym(h, "SecTranslocateCreateOriginalPathForURL") else { return nil }
    let fn = unsafeBitCast(sym, to: OrigFn.self)
    var err: Unmanaged<CFError>?
    guard let r = fn(Bundle.main.bundleURL as CFURL, &err) else { return nil }
    return r.takeRetainedValue() as URL
}

/// translocation から自力で復帰する。
///
/// quarantine が付いたままの .app は、/Applications へ入れてあっても読み取り専用の
/// 一時パスへコピーされて実行される（実測: docs/DMG_DISTRIBUTION_2026-08-30.md §6）。
/// この状態ではセットアップを実行できないため、従来は案内を出して止めるだけだった。
/// だが購入者にとっては「開いても先へ進めない」ままなので、
///   1. 元の .app の quarantine を落とす
///   2. そちらを新しいインスタンスとして開き直す
///   3. 自分は終了する
/// をアプリ自身にやらせる。落とせなかった場合だけ案内アラートへ落ちる。
///
/// 戻り値 true = 開き直しを仕掛けたので、呼び出し側は以降の処理をしてはいけない。
func recoverFromTranslocation() -> Bool {
    guard selfExecutablePath().contains("/AppTranslocation/") else { return false }
    guard let orig = originalBundleURL() else { return false }
    let path = orig.path
    // 元パスが自分自身（＝解決できていない）や、消えている場合は復帰できない
    guard path != Bundle.main.bundleURL.path,
          !path.contains("/AppTranslocation/"),
          FileManager.default.fileExists(atPath: path) else { return false }
    // DMG の中から直接起動された場合は、消しても読み取り専用なので意味がない
    guard !path.hasPrefix("/Volumes/") else { return false }

    do { try stripQuarantine(path) }
    catch { return false }
    guard !hasQuarantine(path) else { return false }   // 落とせなければ案内へ

    let cfg = NSWorkspace.OpenConfiguration()
    // 自分（translocated 版）がまだ生きているので、指定しないと LaunchServices が
    // こちらをアクティベートし直すだけになり、元の .app が起動しない。
    cfg.createsNewApplicationInstance = true
    cfg.activates = true
    NSWorkspace.shared.openApplication(at: orig, configuration: cfg) { _, _ in
        DispatchQueue.main.async { NSApp.terminate(nil) }
    }
    return true
}

struct SetupResult {
    var manifests: [String]
    var extensionDir: String
    var hostPath: String
    var warnings: [String]
    var removedLegacyManifests: [String]
}

func runSetup(browserDirs: [String], cleanupLegacy: Bool = true) throws -> SetupResult {
    if let problem = translocationProblem() { throw HostError(problem) }
    let hostPath = selfExecutablePath()
    // manifest は原子的に書く。同じ固定パスの host を先に登録してから拡張を交換すれば、
    // 再インストール途中で拡張展開に失敗しても旧拡張と既存 host の組は動作を続けられる。
    let manifests = try installHostManifest(into: browserDirs, hostPath: hostPath)
    let ext = try installExtension()
    let legacy = cleanupLegacy ? uninstallHostManifest(from: legacyBrowserDirs()) : RemovalResult()
    let cleanupWarnings = legacy.failures.map {
        "旧ブラウザ登録を削除できなかった: \($0["path"] ?? "?"): \($0["error"] ?? "不明")"
    }
    return SetupResult(manifests: manifests, extensionDir: ext.path, hostPath: hostPath,
                       warnings: ext.warnings + cleanupWarnings,
                       removedLegacyManifests: legacy.removed)
}

// MARK: - doctor（サポート用の自己診断）

func doctorReport() -> [String: Any] {
    let fm = FileManager.default
    var found: [[String: Any]] = []
    for dir in defaultBrowserDirs() {
        let f = "\(dir)/NativeMessagingHosts/\(HOST_NAME).json"
        guard fm.fileExists(atPath: f) else { continue }
        var pathInManifest = ""
        if let d = fm.contents(atPath: f),
           let j = try? JSONSerialization.jsonObject(with: d) as? [String: Any] {
            pathInManifest = (j["path"] as? String) ?? ""
        }
        found.append(["manifest": f, "path": pathInManifest,
                      "path_exists": fm.fileExists(atPath: pathInManifest)])
    }
    var r: [String: Any] = [
        "host_version": HOST_VERSION,
        "self": selfExecutablePath(),
        "extension_dir": EXT_INSTALL_DIR,
        "extension_installed": fm.fileExists(atPath: "\(EXT_INSTALL_DIR)/manifest.json"),
        "extension_id": EXT_ID,
        "native_messaging_manifests": found,
        "translocated": selfExecutablePath().contains("/AppTranslocation/"),
    ]
    let legacy = legacyBrowserDirs().compactMap { dir -> String? in
        let f = "\(dir)/NativeMessagingHosts/\(HOST_NAME).json"
        return fm.fileExists(atPath: f) ? f : nil
    }
    if !legacy.isEmpty { r["legacy_native_messaging_manifests"] = legacy }
    if let problem = translocationProblem() { r["install_blocked"] = problem }
    do {
        let wins = try listWindows()
        r["chrome_running"] = true
        r["windows"] = wins.map { $0.dict }
        r["automation_permission"] = true
    } catch let e as HostError {
        r["chrome_running"] = !e.message.contains("起動していない")
        r["automation_permission"] = !e.message.contains("-1743")
        r["error"] = e.message
    } catch {
        r["error"] = "\(error)"
    }
    return r
}

// MARK: - GUI セットアップ（Finder からダブルクリックされたとき）

/// applicationDidFinishLaunching は、LaunchServices が送ってくる kAEOpenApplication
/// （'oapp'）Apple Event のハンドラの **内側** から呼ばれる。実測したスタックは
///
///   -[NSApplication run] → AEProcessAppleEvent → -[NSApplication _handleAEOpenEvent:]
///     → _sendFinishLaunchingNotification → applicationDidFinishLaunching
///       → showSetupAlert() → -[NSAlert runModal]   ← ここから返らない
///
/// （docs/DMG_DISTRIBUTION_2026-08-30.md §6 に sample の全文）。
/// この中で runModal に入ると 'oapp' へ応答を返さないまま、セットアップのファイル I/O
/// まで全部そこでやることになる。Apple Event ハンドラは有限時間で返すべきものなので、
/// ここを塞ぐのは正しくない。次の run loop へ逃がしてから UI を出す。
final class SetupDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ n: Notification) {
        DispatchQueue.main.async {
            NSApp.activate(ignoringOtherApps: true)
            // quarantine 付きで起動された場合はここで自力復帰し、元の .app を開き直す。
            if recoverFromTranslocation() { return }
            showSetupAlert()
            NSApp.terminate(nil)
        }
    }
}

func showSetupAlert() {
    let alert = NSAlert()
    var extDir = EXT_INSTALL_DIR
    var ok = false
    do {
        let r = try runSetup(browserDirs: defaultBrowserDirs())
        extDir = r.extensionDir
        ok = true
        if r.manifests.isEmpty {
            alert.alertStyle = .warning
            alert.messageText = "Chrome が見つかりませんでした"
            alert.informativeText = """
            Google Chrome のプロファイルが見つからないため、\
            ヘルパーの登録先がありません。

            Chrome を一度起動してから、もう一度この App を開いてください。

            拡張本体は次の場所に展開しました:
            \(r.extensionDir)
            \(r.warnings.isEmpty ? "" : "\n\n注意:\n" + r.warnings.joined(separator: "\n"))
            """
        } else {
            alert.alertStyle = .informational
            alert.messageText = "\(PRODUCT_NAME) の準備ができました"
            alert.informativeText = """
            あと 3 ステップで使えます。

            1. Chrome で chrome://extensions を開き、右上の「デベロッパー モード」を ON
            2. 「パッケージ化されていない拡張機能を読み込む」で次のフォルダを選ぶ
               （下のボタンで Finder に表示できます）
               \(r.extensionDir)
            3. ツールバーの \(PRODUCT_NAME) を押して 375 を選ぶ
               →「\(PRODUCT_NAME) が Google Chrome を制御することを求めています」に「許可」

            拡張の ID は \(EXT_ID) に固定されています。
            違う ID になった場合は、読み込んだフォルダが違います。
            \(r.warnings.isEmpty ? "" : "\n\n注意:\n" + r.warnings.joined(separator: "\n"))
            """
        }
    } catch let e as HostError {
        alert.alertStyle = .critical
        alert.messageText = "セットアップを実行できません"
        alert.informativeText = e.message
    } catch {
        alert.alertStyle = .critical
        alert.messageText = "セットアップに失敗しました"
        alert.informativeText = "\(error)"
    }

    if ok { alert.addButton(withTitle: "拡張フォルダを Finder で開く") }
    alert.addButton(withTitle: "閉じる")
    if ok && alert.runModal() == .alertFirstButtonReturn {
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: extDir)])
    } else if !ok {
        _ = alert.runModal()
    }
}

func guiSetup() {
    let app = NSApplication.shared
    app.setActivationPolicy(.regular)
    let delegate = SetupDelegate()
    app.delegate = delegate
    app.run()
}

// MARK: - CLI

let USAGE = """
\(PRODUCT_NAME) helper \(HOST_VERSION)

  viewport-break <幅>              現在の Chrome ウィンドウを指定幅にする（高さは維持）
  viewport-break <幅> <高さ>       幅と高さ
  viewport-break --list            Chrome の全ウィンドウを表示
  viewport-break --get             現在のウィンドウの bounds
  viewport-break --restore [幅]    一番狭いウィンドウを 1280px（既定）へ戻す — 緊急復帰
  viewport-break --install         native messaging host を登録し、拡張を展開する
  viewport-break --uninstall       登録と展開済みファイルを削除する
  viewport-break --doctor          設置状況・権限・ウィンドウを自己診断
  viewport-break --version
  --json を付けると結果を JSON で出す
  --chrome-dir <path> を付けると設置先の Chrome user data dir を明示する（テスト用・複数可）

引数なし（Finder から起動）で GUI セットアップ。
Chrome から chrome-extension://... 付きで起動されると native messaging host になる。
"""

func emit(_ obj: [String: Any], _ human: String, json: Bool) {
    if json,
       let d = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys]),
       let s = String(data: d, encoding: .utf8) {
        print(s)
    } else {
        print(human)
    }
}

func cli(_ argv: [String]) -> Int32 {
    var args = argv
    let json = args.contains("--json")
    args.removeAll { $0 == "--json" }

    // --chrome-dir は複数回書ける
    var chromeDirs: [String] = []
    var i = 0
    while i < args.count {
        if args[i] == "--chrome-dir", i + 1 < args.count {
            chromeDirs.append(args[i + 1])
            args.removeSubrange(i...(i + 1))
        } else { i += 1 }
    }
    let hasCustomBrowserDirs = !chromeDirs.isEmpty
    let dirs = hasCustomBrowserDirs ? chromeDirs : defaultBrowserDirs()

    guard let head = args.first else { print(USAGE); return 0 }

    do {
        switch head {
        case "-h", "--help":
            print(USAGE); return 0

        case "--version":
            emit(["version": HOST_VERSION, "extension_id": EXT_ID, "impl": "swift"],
                 HOST_VERSION, json: json)
            return 0

        case "--install":
            let r = try runSetup(browserDirs: dirs, cleanupLegacy: !hasCustomBrowserDirs)
            let installOK = !r.manifests.isEmpty
            emit(["ok": installOK, "manifests": r.manifests, "extension_dir": r.extensionDir,
                  "host_path": r.hostPath, "extension_id": EXT_ID,
                  "warnings": r.warnings,
                  "removed_legacy_manifests": r.removedLegacyManifests],
                 ([" host: \(r.hostPath)", " 拡張: \(r.extensionDir)"]
                  + r.manifests.map { " 設置: \($0)" }
                  + r.removedLegacyManifests.map { " 旧登録を削除: \($0)" }
                  + r.warnings.map { " 警告: \($0)" }).joined(separator: "\n"),
                 json: json)
            return installOK ? 0 : 1

        case "--uninstall":
            // 1.0.0 が誤って登録した Chromium 系ブラウザも、既定アンインストールでは掃除する。
            let uninstallDirs = hasCustomBrowserDirs ? dirs : allKnownBrowserDirs()
            let result = uninstallProduct(from: uninstallDirs)
            let human = result.removed.isEmpty && result.failures.isEmpty
                ? "削除するものは無かった"
                : (result.removed.map { "削除: \($0)" }
                   + result.failures.map {
                       "削除失敗: \($0["path"] ?? "?"): \($0["error"] ?? "不明")"
                   }).joined(separator: "\n")
            emit(["ok": result.ok, "removed": result.removed, "failures": result.failures],
                 human,
                 json: json)
            return result.ok ? 0 : 1

        case "--doctor":
            let r = doctorReport()
            if json {
                emit(r, "", json: true)
            } else {
                let d = try JSONSerialization.data(withJSONObject: r,
                                                   options: [.prettyPrinted, .sortedKeys])
                print(String(data: d, encoding: .utf8) ?? "")
            }
            return 0

        case "--list":
            let ws = try listWindows()
            emit(["ok": true, "windows": ws.map { $0.dict }],
                 ws.isEmpty ? "(ウィンドウ無し)"
                            : ws.map { "id=\($0.id)  \($0.width)x\($0.height)  @(\($0.left),\($0.top))" }
                                .joined(separator: "\n"),
                 json: json)
            return 0

        case "--get":
            let b = try pickWindow(try listWindows(), nil)
            emit(["ok": true, "bounds": b.dict],
                 "\(b.width)x\(b.height) @(\(b.left),\(b.top))", json: json)
            return 0

        case "--restore":
            let w = args.count > 1 ? Int(args[1]) : nil
            let r = try restoreWidth(w)
            emit(["ok": true, "restored_to": r.after.width,
                  "before": r.before.dict, "bounds": r.after.dict],
                 "\(r.before.width)px → \(r.after.width)px に戻した"
                 + "（id=\(r.after.id) @(\(r.after.left),\(r.after.top))）", json: json)
            return 0

        default:
            guard let w = Int(head), head.allSatisfy({ $0.isNumber }) else {
                FileHandle.standardError.write(USAGE.data(using: .utf8)!)
                return 2
            }
            let h = args.count > 1 ? Int(args[1]) : nil
            let b = try setWidth(w, height: h, match: nil)
            let ok = b.width == w
            emit(["ok": ok, "requested": w, "bounds": b.dict],
                 "\(b.width)x\(b.height) @(\(b.left),\(b.top))"
                 + (ok ? "" : "  ← 要求 \(w) に到達せず"), json: json)
            return ok ? 0 : 1
        }
    } catch let e as HostError {
        if json { emit(["ok": false, "error": e.message], "", json: true) }
        else { FileHandle.standardError.write("エラー: \(e.message)\n".data(using: .utf8)!) }
        return 1
    } catch {
        if json { emit(["ok": false, "error": "\(error)"], "", json: true) }
        else { FileHandle.standardError.write("エラー: \(error)\n".data(using: .utf8)!) }
        return 1
    }
}

// MARK: - エントリポイント

let argv = Array(CommandLine.arguments.dropFirst())

// Chrome は host を `<path> chrome-extension://<id>/` の形で起動する。
// 「引数があるか」では CLI と区別できないので、この形かどうかで判定する。
if argv.first?.hasPrefix("chrome-extension://") == true || argv.first?.hasPrefix("--parent-window") == true {
    serve()
    exit(0)
}

// Finder / LaunchServices からの起動（引数なし、または -psn_*）は GUI セットアップ。
if argv.isEmpty || argv.first?.hasPrefix("-psn_") == true {
    guiSetup()
    exit(0)
}

exit(cli(argv))
