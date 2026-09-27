package com.ace77505.flutter

import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.net.Uri
import android.provider.DocumentsContract
import android.util.Log
import java.io.*
import java.text.SimpleDateFormat
import java.util.*
import java.util.zip.CRC32
import java.util.zip.Deflater
import java.util.zip.ZipEntry
import java.util.zip.ZipInputStream
import java.util.zip.ZipOutputStream

/**
 * Flutter 应用分析引擎。
 * 纯 I/O + 状态管理，不依赖任何 Android UI 组件。
 */
class FlutterAnalyzer(private val context: Context) {

    companion object {
        private const val TAG = "FlutterAnalyzer"
        private const val SP_NAME = "flutter_blutter_prefs"
        private const val KEY_OUTPUT_DIR_URI = "output_dir_uri"
        private const val KEY_OUTPUT_DIR_NAME = "output_dir_name"
        private const val KEY_INPUT_TYPE = "input_type"
        private const val KEY_INPUT_URI = "input_uri"
        private const val KEY_INPUT_FILE_NAME = "input_file_name"
        private const val KEY_LAST_ZIP_URI = "last_zip_uri"
        private const val KEY_ZIP_COMPRESSION = "zip_compression"
    }

    val baseDir: String = context.filesDir.absolutePath
    private val prefs: SharedPreferences =
        context.getSharedPreferences(SP_NAME, Context.MODE_PRIVATE)

    // ── 读取持久化状态 ──────────────────────────────────────────────

    fun isEnvImported(): Boolean =
        File(getNativeLibDir() + "/libc++_shared.so").exists()

    fun getOutputDirUri(): String? =
        prefs.getString(KEY_OUTPUT_DIR_URI, null)

    fun getOutputDirName(): String? =
        prefs.getString(KEY_OUTPUT_DIR_NAME, null)

    fun getInputType(): String? =
        prefs.getString(KEY_INPUT_TYPE, null)

    fun getInputFileName(): String? =
        prefs.getString(KEY_INPUT_FILE_NAME, null)

    fun getInputUri(): String? =
        prefs.getString(KEY_INPUT_URI, null)

    fun getLastZipUri(): String? =
        prefs.getString(KEY_LAST_ZIP_URI, null)

    // ── 写入持久化状态 ──────────────────────────────────────────────

    private fun save(key: String, value: String) {
        prefs.edit().putString(key, value).apply()
    }

    fun saveInputPrefs(type: String, uri: String, fileName: String) {
        prefs.edit()
            .putString(KEY_INPUT_TYPE, type)
            .putString(KEY_INPUT_URI, uri)
            .putString(KEY_INPUT_FILE_NAME, fileName)
            .apply()
    }

    fun saveOutputDirPrefs(uriStr: String, displayName: String) {
        prefs.edit()
            .putString(KEY_OUTPUT_DIR_URI, uriStr)
            .putString(KEY_OUTPUT_DIR_NAME, displayName)
            .apply()
    }

    fun saveLastZipPrefs(uriStr: String) {
        prefs.edit().putString(KEY_LAST_ZIP_URI, uriStr).apply()
    }

    // ── ZIP 压缩 ───────────────────────────────────────────────────

    fun isZipCompressionEnabled(): Boolean =
        prefs.getBoolean(KEY_ZIP_COMPRESSION, false)

    fun setZipCompression(enabled: Boolean) {
        prefs.edit().putBoolean(KEY_ZIP_COMPRESSION, enabled).apply()
    }

    // ── 从 APK 提取 libapp.so ──────────────────────────────────────

    /** 从 APK 提取 libapp.so 和 libflutter.so */
    suspend fun extractLibFromApk(uri: Uri): Boolean {
        val inputDir = File("$baseDir/input").also {
            it.mkdirs()
            it.listFiles()?.forEach { f -> f.delete() }
        }

        val targets = mapOf(
            "lib/arm64-v8a/libapp.so" to "libapp.so",
            "lib/armeabi-v7a/libapp.so" to "libapp.so",
            "lib/arm64-v8a/libflutter.so" to "libflutter.so",
            "lib/armeabi-v7a/libflutter.so" to "libflutter.so",
        )
        val extracted = mutableSetOf<String>()

        ZipInputStream(context.contentResolver.openInputStream(uri)).use { zip ->
            var entry = zip.nextEntry
            while (entry != null) {
                val localName = targets[entry.name]
                if (localName != null && localName !in extracted) {
                    File(inputDir, localName).outputStream().use { zip.copyTo(it) }
                    File(inputDir, localName).setExecutable(true, false)
                    extracted.add(localName)
                }
                zip.closeEntry()
                entry = zip.nextEntry
            }
        }

        return "libapp.so" in extracted
    }

    // ── 从 SAF 目录选取 SO ─────────────────────────────────────────

    data class SoCandidate(val uri: Uri, val fileName: String)

    /** 列出 SAF 树目录下的 .so 文件，返回候选列表 */
    suspend fun listSoCandidates(treeUri: Uri): List<SoCandidate> {
        val treeId = DocumentsContract.getTreeDocumentId(treeUri)
        val childrenUri = DocumentsContract.buildChildDocumentsUriUsingTree(treeUri, treeId)
        val result = mutableListOf<SoCandidate>()

        val cursor = context.contentResolver.query(childrenUri, null, null, null, null)
        cursor?.use { c ->
            while (c.moveToNext()) {
                val name = c.getString(
                    c.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DISPLAY_NAME)
                )
                val docId = c.getString(
                    c.getColumnIndexOrThrow(DocumentsContract.Document.COLUMN_DOCUMENT_ID)
                )
                if (name == "libapp.so" || name.endsWith(".so")) {
                    val soUri = DocumentsContract.buildDocumentUriUsingTree(treeUri, docId)
                    result.add(SoCandidate(soUri, name))
                }
            }
        }
        return result
    }

    /** 将 SAF 树目录中的 libapp.so 和 libflutter.so 复制到内部 input 目录 */
    suspend fun copySoDirToInput(treeUri: Uri, soCandidates: List<SoCandidate>) {
        val inputDir = File("$baseDir/input").also {
            it.mkdirs()
            it.listFiles()?.forEach { f -> f.delete() }
        }

        // 复制 libapp.so
        val appCandidate = soCandidates.find { it.fileName == "libapp.so" }
        if (appCandidate != null) {
            context.contentResolver.openInputStream(appCandidate.uri)?.use { input ->
                File(inputDir, "libapp.so").outputStream().use { input.copyTo(it) }
            }
            File(inputDir, "libapp.so").setExecutable(true, false)
        }

        // 复制 libflutter.so（如果存在）
        val flutterCandidate = soCandidates.find { it.fileName == "libflutter.so" }
        if (flutterCandidate != null) {
            context.contentResolver.openInputStream(flutterCandidate.uri)?.use { input ->
                File(inputDir, "libflutter.so").outputStream().use { input.copyTo(it) }
            }
            File(inputDir, "libflutter.so").setExecutable(true, false)
        }
    }

    // ── 输出目录 ────────────────────────────────────────────────────

    /** 持久化 SAF 树 URI 权限 */
    fun persistOutputDirUri(uri: Uri) {
        // 官方标准：take 只传 READ|WRITE（不带 PERSISTABLE）。
        // PERSISTABLE 是在启动 intent 的 addFlags 上加的；本会话内系统已授予，
        // 因此这里能成功持久化，重启后无需再选。
        val flags = Intent.FLAG_GRANT_READ_URI_PERMISSION or
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION
        try {
            context.contentResolver.takePersistableUriPermission(uri, flags)
            android.util.Log.i("FlutterAnalyzer", "takePersistableUriPermission OK for $uri")
        } catch (e: Exception) {
            // 若系统本次未授予 PERSISTABLE（异常 ROM），授权无法持久化（仅本会话有效）。
            // 这里不 crash，目录 URI 仍会保存；重启后需重选。
            android.util.Log.w("FlutterAnalyzer",
                "takePersistableUriPermission failed: $uri -> ${e.message}", e)
        }
    }

    /** 从 SAF 树 URI 提取可读路径 */
    fun extractDisplayPath(uri: Uri): String {
        return try {
            val docId = DocumentsContract.getTreeDocumentId(uri)
            docId.substringAfter(":").ifBlank { uri.lastPathSegment ?: uri.toString() }
        } catch (_: Exception) {
            uri.lastPathSegment ?: uri.toString()
        }
    }

    /** 从 SAF 文件 URI 提取文件名 */
    fun extractFileName(uri: Uri): String {
        val path = uri.lastPathSegment ?: return "unknown"
        val decoded = Uri.decode(path)
        return decoded.substringAfterLast(':').substringAfterLast('/')
    }

    // ── 运行分析 ────────────────────────────────────────────────────

    /** 运行 blutter：从 nativeLibraryDir exec 全静态 ELF，无 noexec 问题 */
    suspend fun runAnalysis(onLogLine: (String) -> Unit): Int {
        val outDir = File("$baseDir/out").also {
            it.deleteRecursively()
            it.mkdirs()
        }
        val libapp = "$baseDir/input/libapp.so"
        val nativeDir = getNativeLibDir()

        // 检测 Dart 版本，定位对应的 .so
        val dartVer = detectDartVersion("$baseDir/input/libflutter.so", libapp)
        val verSafe = if (dartVer.isNotEmpty()) dartVer.replace(".", "_") else "3_12_2"
        val binaryName = "libblutter_${verSafe}.so"
        val binaryPath = "$nativeDir/$binaryName"

        if (!File(binaryPath).exists()) {
            onLogLine("❌ 未找到 $binaryName")
            return 1
        }
        onLogLine("🔍 Dart ${if (dartVer.isNotEmpty()) dartVer else verSafe} → $binaryName")

        // bionic 动态版: 直接 execve（interpreter=/system/bin/linker64）
        // linker64 不自动搜索 nativeLibraryDir，需显式 LD_LIBRARY_PATH（仅影响 execve 的子进程）
        val process = ProcessBuilder(binaryPath, "-i", libapp, "-o", "$baseDir/out")
            .directory(File("$baseDir/out"))
            .redirectErrorStream(true)
        process.environment()["LD_LIBRARY_PATH"] = nativeDir

        val proc = process.start()
        proc.inputStream.bufferedReader().use { reader ->
            reader.forEachLine { line -> onLogLine(line) }
        }
        return proc.waitFor()
    }

    /** 检查运行条件是否满足 */
    fun checkPrerequisites(): String? {
        if (!isEnvImported()) return "内置运行库未部署（libc++_shared.so 未在 nativeLibDir）"
        if (getOutputDirUri() == null) return "请先选择输出目录"
        if (!File("$baseDir/input/libapp.so").exists()) return "请先选择 APK 或 SO 目录"
        return null
    }

    // ── 打包 + 导出 ZIP ────────────────────────────────────────────

    /** 打包 out/ 目录为无压缩 ZIP，写入 SAF 输出目录。返回 ZIP 文件名，失败返回 null */
    suspend fun zipAndExport(): String? {
        val outDir = File("$baseDir/out")
        val files = outDir.listFiles() ?: emptyArray()
        if (files.isEmpty()) return null

        val treeUriStr = getOutputDirUri() ?: return null
        // 保留授权的原始编码 URI（含 %3A），切勿还原成 ":"。
        val outputTreeUri = Uri.parse(treeUriStr)
        // 官方要求:createDocument 的 parent 必须是 buildDocumentUriUsingTree 得到的
        // document URI(content://.../tree/<id>/document/<id>), 而不是裸 tree URI,
        // 否则 provider 报 Invalid URI。
        val parentDocUri = DocumentsContract.buildDocumentUriUsingTree(
            outputTreeUri, DocumentsContract.getTreeDocumentId(outputTreeUri)
        )
        val timestamp = SimpleDateFormat("yyyyMMdd_HHmmss", Locale.getDefault()).format(Date())
        val zipName = "blutter_output_$timestamp.zip"

        val zipUri = try {
            DocumentsContract.createDocument(
                context.contentResolver, parentDocUri,
                "application/zip", zipName
            )
        } catch (e: IllegalArgumentException) {
            android.util.Log.w("FlutterAnalyzer", "createDocument failed for tree=${outputTreeUri} parent=${parentDocUri}: ${e.message}", e)
            throw IllegalStateException("输出目录不可写（${zipName}）：${e.message}。请到设置重新选择输出目录", e)
        } ?: return null

        context.contentResolver.openOutputStream(zipUri)?.use { outputStream ->
            BufferedOutputStream(outputStream).use { bos ->
                ZipOutputStream(bos).use { zos ->
                    val useCompression = isZipCompressionEnabled()
                    if (!useCompression) zos.setLevel(Deflater.NO_COMPRESSION)
                    var totalFiles = 0
                    var totalBytes = 0L

                    outDir.walkTopDown().forEach { file ->
                        if (file.isFile) {
                            val relativePath = file.relativeTo(outDir).path
                            val entry = ZipEntry(relativePath)
                            val bytes = file.readBytes()
                            if (!useCompression) {
                                entry.method = ZipEntry.STORED
                                entry.size = bytes.size.toLong()
                                entry.compressedSize = bytes.size.toLong()
                                entry.crc = CRC32().apply { update(bytes) }.value
                            }

                            zos.putNextEntry(entry)
                            zos.write(bytes)
                            zos.closeEntry()
                            totalFiles++
                            totalBytes += bytes.size
                        }
                    }
                }
            }
        }

        saveLastZipPrefs(zipUri.toString())
        return zipName
    }

    /** 打包统计：文件数和总字节 */
    fun getOutputStats(): Pair<Int, Long> {
        val outDir = File("$baseDir/out")
        var files = 0
        var bytes = 0L
        outDir.walkTopDown().forEach { f ->
            if (f.isFile) { files++; bytes += f.length() }
        }
        return files to bytes
    }

    /**
     * 分析产物完整性自检：统计 out/asm 中「无代码」方法（`size: -0x1`，即 blutter
     * 读到 Code.Size()==-1 而跳过反汇编）的占比。占比过高通常意味着目标 app 已混淆，
     * blutter 无法还原其大部分函数——这是 **工具能力限制**，**不影响产物生成**，
     * 文件仍会照常输出，但反汇编内容可能不完整。
     *
     * @return 需要提示时的多行警告文本；正常/无法判定时返回 null
     */
    fun detectUnreliableResult(thresholdPct: Int = 70): String? {
        val asmDir = File("$baseDir/out/asm")
        if (!asmDir.isDirectory) return null

        val re = Regex("""// \*\* addr: 0x[0-9a-f]+, size: (-?)0x[0-9a-f]+""")
        var total = 0
        var noCode = 0
        asmDir.walkTopDown().forEach { f ->
            if (f.isFile && f.name.endsWith(".dart")) {
                f.forEachLine { line ->
                    re.find(line)?.let { m ->
                        total++
                        if (m.groupValues[1] == "-") noCode++
                    }
                }
            }
        }

        if (total == 0) return null
        val pct = noCode * 100 / total
        if (pct < thresholdPct) return null

        return buildString {
            append("⚠ 完整性提示：约 $pct% 的函数未被反汇编（$noCode/$total）\n")
            append("⚠ 目标应用可能已混淆，blutter 无法还原其大部分函数（工具能力限制）\n")
            append("⚠ 这不影响产物生成，文件仍照常输出；但反汇编内容可能不完整，请谨慎参考")
        }
    }

    /** 获取 native lib 目录（ld-linux 所在目录，非 noexec） */
    fun getNativeLibDir(): String {
        return try {
            val ai = context.packageManager.getApplicationInfo(context.packageName, 0)
            ai.nativeLibraryDir
        } catch (_: Exception) {
            "/data/app/${context.packageName}/lib/arm64"
        }
    }

    /** 规范化 SAF 树 URI：`/tree/msd%3A11811` 这类把冒号编码了的 URI，
     *  需还原为 `/tree/msd:11811` 才能被 DocumentsContract 正确识别。 */
    /** 从 libflutter.so 或 libapp.so 二进制中 grep Dart 版本号 */
    private fun detectDartVersion(vararg candidates: String): String {
        // 与 blutter 官方 extract_dart_info.py 一致：版本串前需 \x00 分隔（避免匹配次要版本串）
        val pattern = Regex("""\u0000(\d+\.\d+\.\d+) \(stable\)""").toPattern()
        for (path in candidates) {
            val file = File(path)
            if (!file.exists()) continue
            try {
                val bytes = file.readBytes()
                val text = String(bytes, Charsets.ISO_8859_1)
                val matcher = pattern.matcher(text)
                if (matcher.find()) {
                    return matcher.group(1)
                }
            } catch (_: Exception) { }
        }
        return ""
    }
}
