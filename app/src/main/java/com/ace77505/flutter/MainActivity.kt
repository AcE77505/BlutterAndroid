package com.ace77505.flutter

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.SpannableString
import android.text.Spanned
import android.text.style.ForegroundColorSpan
import android.text.style.StyleSpan
import android.view.Menu
import android.view.MenuItem
import android.widget.ScrollView
import android.widget.TextView
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import java.io.File
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import com.google.android.material.button.MaterialButton
import com.google.android.material.card.MaterialCardView
import com.google.android.material.snackbar.Snackbar
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import androidx.core.net.toUri

class MainActivity : AppCompatActivity() {

    private lateinit var btnSelectApk: MaterialButton
    private lateinit var btnSelectSoDir: MaterialButton
    private lateinit var cardStatus: MaterialCardView
    private lateinit var tvStatus: TextView
    private lateinit var btnRun: MaterialButton
    private lateinit var tvLog: TextView
    private lateinit var scrollLog: ScrollView
    private lateinit var btnCopyOutput: MaterialButton
    private lateinit var btnShare: MaterialButton

    private lateinit var analyzer: FlutterAnalyzer

    private val apkLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocument()
    ) { uri: Uri? -> uri?.let { extractLibFromApk(it) } }

    private val soDirLauncher = registerForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri: Uri? -> uri?.let { browseSoDir(it) } }

    // ── Lifecycle ──────────────────────────────────────────────────

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        analyzer = FlutterAnalyzer(this)
        setSupportActionBar(findViewById(R.id.toolbar))
        initViews()
        showStartupStatus()
    }

    override fun onResume() {
        super.onResume()
        // 从设置页返回后刷新顶部状态
        refreshStatusHeader()
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == R.id.action_settings) {
            startActivity(Intent(this, SettingsActivity::class.java))
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    // ── Views ──────────────────────────────────────────────────────

    private fun initViews() {
        btnSelectApk = findViewById(R.id.btnSelectApk)
        btnSelectSoDir = findViewById(R.id.btnSelectSoDir)
        cardStatus = findViewById(R.id.cardStatus)
        tvStatus = findViewById(R.id.tvStatus)
        btnRun = findViewById(R.id.btnRun)
        tvLog = findViewById(R.id.tvLog)
        scrollLog = findViewById(R.id.scrollLog)
        btnCopyOutput = findViewById(R.id.btnOpenOutput)
        btnShare = findViewById(R.id.btnShare)

        btnSelectApk.setOnClickListener {
            apkLauncher.launch(arrayOf(
                "application/vnd.android.package-archive", "application/zip"
            ))
        }
        btnSelectSoDir.setOnClickListener {
            soDirLauncher.launch(null)
        }
        btnRun.setOnClickListener { runAnalysis() }
        btnCopyOutput.setOnClickListener { copyLogToClipboard() }
        btnShare.setOnClickListener { shareOutputZip() }

        // 恢复输入状态
        val inputType = analyzer.getInputType()
        val inputName = analyzer.getInputFileName()
        val inputUri = analyzer.getInputUri()
        if (inputType != null && inputName != null && inputUri != null) {
            showInputStatus(inputType, inputUri, inputName)
        }
        btnShare.isEnabled = analyzer.getLastZipUri() != null
    }

    private fun showStartupStatus() {
        val envOk = analyzer.isEnvImported()
        val outDir = analyzer.getOutputDirUri()
        log("内置运行库: ${if (envOk) "✅ 已部署" else "❌ 缺失"}")
        log("输出目录: ${if (outDir != null) "📂 $outDir" else "❌ 未配置"}")
        log("")
        log("选择 APK 或 SO 目录后点击运行分析")
    }

    private fun refreshStatusHeader() {
        // 只在日志为空时重写状态（从设置页返回时）
        if (tvLog.text.isNullOrEmpty()) {
            showStartupStatus()
        }
    }

    // ── 从 APK 提取 ────────────────────────────────────────────────

    private fun extractLibFromApk(uri: Uri) {
        tvLog.text = ""
        showStartupStatus()
        btnSelectApk.isEnabled = false
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val found = analyzer.extractLibFromApk(uri)
                withContext(Dispatchers.Main) {
                    if (found) {
                        val name = analyzer.extractFileName(uri)
                        analyzer.saveInputPrefs("APK", uri.toString(), name)
                        showInputStatus("APK", uri.toString(), name)
                        val hasFlutter = File(analyzer.baseDir + "/input/libflutter.so").exists()
                        log("✅ 已提取 libapp.so${if (hasFlutter) " + libflutter.so" else ""}")
                    } else {
                        Snackbar.make(btnRun, "APK 中未找到 libapp.so", Snackbar.LENGTH_LONG).show()
                        log("❌ APK 中无 libapp.so")
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Snackbar.make(btnRun, "提取失败: ${e.message}", Snackbar.LENGTH_LONG).show()
                }
            } finally {
                withContext(Dispatchers.Main) { btnSelectApk.isEnabled = true }
            }
        }
    }

    // ── 从目录浏览 SO ──────────────────────────────────────────────

    private fun browseSoDir(treeUri: Uri) {
        tvLog.text = ""
        showStartupStatus()
        btnSelectSoDir.isEnabled = false
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val candidates = analyzer.listSoCandidates(treeUri)
                val hasApp = candidates.any { it.fileName == "libapp.so" }
                if (!hasApp) {
                    withContext(Dispatchers.Main) {
                        Snackbar.make(btnRun, "目录中未找到 libapp.so", Snackbar.LENGTH_LONG).show()
                    }
                    return@launch
                }
                analyzer.copySoDirToInput(treeUri, candidates)
                val app = candidates.first { it.fileName == "libapp.so" }
                withContext(Dispatchers.Main) {
                    analyzer.saveInputPrefs("SO目录", app.uri.toString(), app.fileName)
                    showInputStatus("SO目录", app.uri.toString(), app.fileName)
                    val hasFlutter = candidates.any { it.fileName == "libflutter.so" }
                    log("✅ 已复制 libapp.so${if (hasFlutter) " + libflutter.so" else ""}")
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    Snackbar.make(btnRun, "读取目录失败: ${e.message}", Snackbar.LENGTH_LONG).show()
                }
            } finally {
                withContext(Dispatchers.Main) { btnSelectSoDir.isEnabled = true }
            }
        }
    }

    // ── 状态栏显示 ──────────────────────────────────────────────────

    private fun showInputStatus(type: String, uri: String, fileName: String) {
        val text = "已选择 $type：${uri}\n  └── $fileName ──"
        val ss = SpannableString(text)
        val idx = text.indexOf(fileName, text.indexOf("└──"))
        if (idx >= 0) {
            ss.setSpan(
                ForegroundColorSpan(ContextCompat.getColor(this, R.color.highlight)),
                idx, idx + fileName.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
            )
            ss.setSpan(
                StyleSpan(android.graphics.Typeface.BOLD),
                idx, idx + fileName.length, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE
            )
        }
        tvStatus.text = ss
        cardStatus.visibility = TextView.VISIBLE
    }

    // ── 运行分析 ────────────────────────────────────────────────────

    private fun runAnalysis() {
        val err = analyzer.checkPrerequisites()
        if (err != null) {
            Snackbar.make(btnRun, err, Snackbar.LENGTH_LONG).show()
            return
        }

        btnRun.isEnabled = false
        tvLog.text = ""
        btnShare.isEnabled = false

        // 日志头部：状态 + 执行命令
        val envOk = analyzer.isEnvImported()
        val outDir = analyzer.getOutputDirUri()
        log("内置运行库: ${if (envOk) "✅ 已部署" else "❌ 缺失"}")
        log("输出目录: ${if (outDir != null) "📂 $outDir" else "❌ 未配置"}")
        log("")
        log("执行: libblutter_X_X_X.so -i ../input/libapp.so -o ../out")
        log("")

        val startTime = System.currentTimeMillis()

        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val exitCode = analyzer.runAnalysis { line ->
                    runOnUiThread { log(line) }
                }

                withContext(Dispatchers.Main) {
                    if (exitCode == 0) {
                        val elapsed = System.currentTimeMillis() - startTime
                        log("")
                        log("✅ 分析完成（${elapsed / 1000}s）")

                        // 分析后、打包前：产物完整性自检（疑似混淆 → 结果可能不完整）
                        val qualityWarn = withContext(Dispatchers.IO) {
                            analyzer.detectUnreliableResult()
                        }
                        qualityWarn?.split("\n")?.forEach { log(it) }

                        log("📦 正在打包输出...")

                        lifecycleScope.launch(Dispatchers.IO) { doExport() }
                    } else {
                        log("")
                        log("❌ 分析失败，退出码: $exitCode")
                        btnRun.isEnabled = true
                    }
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    log("❌ 运行异常: ${e.message}")
                    btnRun.isEnabled = true
                }
            }
        }
    }

    private suspend fun doExport() {
        try {
            val (files, bytes) = analyzer.getOutputStats()
            val zipName = analyzer.zipAndExport()

            withContext(Dispatchers.Main) {
                if (zipName != null) {
                    log("✅ 已打包 $files 个文件（${bytes / 1024}KB）")
                    val mode = if (analyzer.isZipCompressionEnabled()) "压缩" else "无压缩"
                    log("📦 $zipName（$mode）")
                    btnShare.isEnabled = true
                } else {
                    log("⚠ 打包失败")
                }
                btnRun.isEnabled = true
            }
        } catch (e: Exception) {
            withContext(Dispatchers.Main) {
                log("❌ 打包异常: ${e.message}")
                btnRun.isEnabled = true
            }
        }
    }

    // ── 复制日志到剪贴板 ──────────────────────────────────────────

    private fun copyLogToClipboard() {
        val text = tvLog.text.toString()
        if (text.isEmpty()) {
            Toast.makeText(this, "日志为空", Toast.LENGTH_SHORT).show()
            return
        }
        val clipboard = getSystemService(CLIPBOARD_SERVICE) as android.content.ClipboardManager
        clipboard.setPrimaryClip(android.content.ClipData.newPlainText("blutter_log", text))
        Toast.makeText(this, "日志已复制到剪贴板", Toast.LENGTH_SHORT).show()
    }

    private fun shareOutputZip() {
        val uriStr = analyzer.getLastZipUri() ?: return
        try {
            startActivity(Intent.createChooser(
                Intent(Intent.ACTION_SEND).apply {
                    type = "application/zip"
                    putExtra(Intent.EXTRA_STREAM, uriStr.toUri())
                    addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                }, "分享分析结果"
            ))
        } catch (_: Exception) {
            Toast.makeText(this, "无法分享文件", Toast.LENGTH_SHORT).show()
        }
    }

    // ── 日志 ────────────────────────────────────────────────────────

    private val tsFormat = java.text.SimpleDateFormat("HH:mm:ss", java.util.Locale.US)

    private fun log(msg: String) {
        val stamp = if (msg.isEmpty()) "" else "[${tsFormat.format(java.util.Date())}] "
        val prev = tvLog.text.toString()
        tvLog.text = if (prev.isEmpty()) "$stamp$msg" else "$prev\n$stamp$msg"
        scrollLog.post { scrollLog.fullScroll(ScrollView.FOCUS_DOWN) }
    }
}
