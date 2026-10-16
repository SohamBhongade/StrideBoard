package com.strideboard.app

import android.annotation.SuppressLint
import android.content.ActivityNotFoundException
import android.content.Intent
import android.graphics.Bitmap
import android.net.Uri
import android.os.Bundle
import android.text.format.DateUtils
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.ProgressBar
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.enableEdgeToEdge
import androidx.core.content.ContextCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/** Main screen: the StrideBoard website full screen, with a slim sync banner on top. */
class MainActivity : ComponentActivity() {

    private lateinit var webView: WebView
    private lateinit var banner: TextView
    private lateinit var offlineView: View
    private lateinit var progress: ProgressBar

    private var loadedBase: String? = null
    private var mainFrameFailed = false
    private var stepsGranted: Boolean? = null
    private var syncing = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // First run: the setup screen comes first.
        if (!Prefs.isConfigured(this)) {
            startActivity(Intent(this, SetupActivity::class.java))
            finish()
            return
        }

        enableEdgeToEdge()
        setContentView(R.layout.activity_main)
        findViewById<View>(R.id.root).padForSystemBars()

        webView = findViewById(R.id.web_view)
        banner = findViewById(R.id.sync_banner)
        offlineView = findViewById(R.id.offline_view)
        progress = findViewById(R.id.progress)

        banner.setOnClickListener { startActivity(Intent(this, SetupActivity::class.java)) }
        findViewById<Button>(R.id.retry_button).setOnClickListener { retry() }

        CookieManager.getInstance().setAcceptCookie(true)
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            // Lets the website tell it is running inside the Android app, if it wants to.
            userAgentString = "$userAgentString StrideBoardAndroid/1.0"
        }
        webView.webChromeClient = WebChromeClient()
        webView.webViewClient = SiteClient()

        // Back button goes back inside the website first.
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (offlineView.visibility != View.VISIBLE && webView.canGoBack()) webView.goBack()
                else finish()
            }
        })

        if (savedInstanceState != null && webView.restoreState(savedInstanceState) != null) {
            loadedBase = Prefs.serverUrl(this)
        } else {
            loadSite()
        }
    }

    override fun onResume() {
        super.onResume()
        if (!::webView.isInitialized) return
        webView.onResume()
        // The address may have changed on the setup screen.
        if (Prefs.serverUrl(this) != loadedBase) loadSite()
        refreshBanner()
        lifecycleScope.launch { syncOnOpen() }
    }

    override fun onPause() {
        if (::webView.isInitialized) {
            webView.onPause()
            CookieManager.getInstance().flush() // keep the website login
        }
        super.onPause()
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        if (::webView.isInitialized) webView.saveState(outState)
    }

    override fun onDestroy() {
        if (::webView.isInitialized) webView.destroy()
        super.onDestroy()
    }

    private fun loadSite() {
        val base = Prefs.serverUrl(this)
        loadedBase = base
        offlineView.visibility = View.GONE
        webView.visibility = View.VISIBLE
        webView.loadUrl("$base/")
    }

    private fun retry() {
        offlineView.visibility = View.GONE
        webView.visibility = View.VISIBLE
        val current = webView.url
        if (current.isNullOrBlank() || current == "about:blank") loadSite() else webView.reload()
    }

    private fun showOffline() {
        progress.visibility = View.GONE
        webView.visibility = View.INVISIBLE
        offlineView.visibility = View.VISIBLE
    }

    /** For phones without background reads: sync when the app opens, at most every 15 minutes. */
    private suspend fun syncOnOpen() {
        val status = StepReader.status(this)
        stepsGranted = status.available && status.stepsGranted
        SyncScheduler.update(this, status.backgroundGranted)
        val dueAt = Prefs.lastAttemptAt(this) + 15 * 60 * 1000L
        if (stepsGranted == true && !syncing && System.currentTimeMillis() >= dueAt) {
            syncing = true
            refreshBanner()
            SyncRunner.run(this, inBackground = false)
            syncing = false
        }
        refreshBanner()
    }

    private fun refreshBanner() {
        val lastSuccess = Prefs.lastSuccessAt(this)
        val now = System.currentTimeMillis()
        val (text, warning) = when {
            syncing -> "Syncing steps…" to false
            stepsGranted == false -> "Step sync is off · tap to set up" to true
            !Prefs.lastOk(this) -> "Step sync needs attention · tap to fix" to true
            lastSuccess == 0L -> "Steps not synced yet · tap to sync" to false
            now - lastSuccess < 60_000 -> "Steps synced just now" to false
            else -> "Steps synced " + DateUtils.getRelativeTimeSpanString(
                lastSuccess, now, DateUtils.MINUTE_IN_MILLIS
            ) to false
        }
        banner.text = text
        banner.setBackgroundColor(
            ContextCompat.getColor(this, if (warning) R.color.banner_warn_bg else R.color.banner_ok_bg)
        )
        banner.setTextColor(
            ContextCompat.getColor(this, if (warning) R.color.banner_warn_text else R.color.banner_ok_text)
        )
    }

    private fun openOutside(uri: Uri) {
        try {
            startActivity(Intent(Intent.ACTION_VIEW, uri))
        } catch (e: ActivityNotFoundException) {
            // No app can open this link; ignore.
        }
    }

    private inner class SiteClient : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val uri = request.url
            val baseHost = Uri.parse(loadedBase ?: "").host
            val sameSite = (uri.scheme == "https" || uri.scheme == "http") &&
                uri.host.equals(baseHost, ignoreCase = true)
            if (sameSite) return false   // stay inside the app
            openOutside(uri)             // other websites, mailto:, tel: open outside
            return true
        }

        override fun onPageStarted(view: WebView, url: String?, favicon: Bitmap?) {
            mainFrameFailed = false
            progress.visibility = View.VISIBLE
        }

        override fun onPageFinished(view: WebView, url: String?) {
            progress.visibility = View.GONE
            if (!mainFrameFailed) {
                offlineView.visibility = View.GONE
                webView.visibility = View.VISIBLE
            }
        }

        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            if (request.isForMainFrame) {
                mainFrameFailed = true
                showOffline()
            }
        }
    }
}
