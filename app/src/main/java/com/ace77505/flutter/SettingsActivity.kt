package com.ace77505.flutter

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.button.MaterialButton
import com.google.android.material.switchmaterial.SwitchMaterial

class SettingsActivity : AppCompatActivity() {

    private lateinit var btnOutputDir: MaterialButton
    private lateinit var tvOutputDirStatus: TextView
    private lateinit var switchZipCompress: SwitchMaterial
    private lateinit var analyzer: FlutterAnalyzer

    // 用 StartActivityForResult + 自建 intent，确保启动时带 PERSISTABLE flag，
    // 才能让 takePersistableUriPermission 在本会话内真正授权（官方 require 的用法）。
    private val outputDirLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (result.resultCode == android.app.Activity.RESULT_OK) {
            result.data?.data?.let { setOutputDir(it) }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        analyzer = FlutterAnalyzer(this)

        btnOutputDir = findViewById(R.id.btnOutputDir)
        tvOutputDirStatus = findViewById(R.id.tvOutputDirStatus)
        switchZipCompress = findViewById(R.id.switchZipCompress)

        findViewById<com.google.android.material.appbar.MaterialToolbar>(R.id.toolbar)
            .setNavigationOnClickListener { finish() }

        btnOutputDir.setOnClickListener {
            // 官方要求：启动 intent 必须带 PERSISTABLE flag，返回的 URI 才可被持久化授权。
            val intent = Intent(Intent.ACTION_OPEN_DOCUMENT_TREE).apply {
                addFlags(
                    Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION or
                    Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
                )
            }
            outputDirLauncher.launch(intent)
        }
        switchZipCompress.setOnCheckedChangeListener { _, checked ->
            analyzer.setZipCompression(checked)
        }

        restoreState()
    }

    private fun restoreState() {
        val outUri = analyzer.getOutputDirUri()
        tvOutputDirStatus.text = if (outUri != null) "📂 $outUri" else "未配置"
        switchZipCompress.isChecked = analyzer.isZipCompressionEnabled()
    }

    private fun setOutputDir(uri: Uri) {
        analyzer.persistOutputDirUri(uri)
        analyzer.saveOutputDirPrefs(uri.toString(), uri.toString())
        tvOutputDirStatus.text = "📂 ${uri.toString()}"
    }
}
