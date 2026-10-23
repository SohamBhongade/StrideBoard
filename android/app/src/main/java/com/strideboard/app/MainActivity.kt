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
import android.webkit.JavascriptInterface
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
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.time.LocalDate

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
    private var liveJob: Job? = null
    private var firstTick = true

    companion object {
        /** While the app is on screen, check Health Connect this often. */
        private const val LIVE_INTERVAL_MS = 30_000L
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // No setup screen first: the app opens the school's website, the person logs in there,
        // and the website hands this app their token (AppBridge below). Nothing to copy or paste.
        Prefs.ensureServer(this)

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
            // StrideBoardApp/<version> lets the website offer an update when a newer app is out.
            userAgentString = "$userAgentString StrideBoardAndroid/1.0 StrideBoardApp/${Updater.versionCode(this@MainActivity)}"
        }
        webView.addJavascriptInterface(AppBridge(), "StrideBoardApp")
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
        startLive()
    }

    override fun onPause() {
        liveJob?.cancel()
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

    /**
     * Live steps: while the app is on screen, read Health Connect every 30 seconds, send any
     * change to the website, and update the numbers on the page in place (no reload).
     * Stops as soon as the app leaves the screen (onPause), so it doesn't drain the battery.
     */
    private fun startLive() {
        liveJob?.cancel()
        firstTick = true
        liveJob = lifecycleScope.launch {
            while (isActive) {
                liveTick()
                delay(LIVE_INTERVAL_MS)
            }
        }
    }

    private suspend fun liveTick() {
        val status = StepReader.status(this)
        stepsGranted = status.available && status.stepsGranted
        if (firstTick) SyncScheduler.update(this, status.backgroundGranted)
        if (stepsGranted == true && !syncing) {
            syncing = firstTick          // only show "Syncing steps…" on the first check
            refreshBanner()
            val outcome = SyncRunner.run(this, inBackground = false)
            syncing = false
            if (outcome == SyncOutcome.SUCCESS || outcome == SyncOutcome.NOTHING_TO_SEND) showLiveSteps()
        }
        firstTick = false
        refreshBanner()
    }

    /** Tell the page today's latest total; the website's app.js updates the numbers. */
    private fun showLiveSteps() {
        if (offlineView.visibility == View.VISIBLE) return
        val steps = Prefs.todayRead(this, LocalDate.now(StepReader.DUBAI).toString())
        if (steps < 0) return
        webView.evaluateJavascript(
            "window.StrideBoard && window.StrideBoard.liveSteps && window.StrideBoard.liveSteps($steps)", null)
    }

    private fun refreshBanner() {
        val lastSuccess = Prefs.lastSuccessAt(this)
        val now = System.currentTimeMillis()
        val (text, warning) = when {
            !Prefs.isConfigured(this) -> "Log in below to link this phone" to false
            syncing -> "Syncing steps…" to false
            stepsGranted == false -> "Step sync is off · tap to set up" to true
            !Prefs.lastOk(this) -> "Step sync needs attention · tap to fix" to true
            lastSuccess == 0L -> "Steps not synced yet · tap to sync" to false
            now - lastSuccess < 60_000 ->
                (if (liveJob?.isActive == true) "Live · your steps update every 30 seconds"
                 else "Steps synced just now") to false
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

    /**
     * Lets the StrideBoard website (and only it) tell the app who is logged in.
     * The website's pages call StrideBoardApp.linkAccount(token) after login.
     */
    private inner class AppBridge {
        /** The website's "Update" button: download the newest app and let Android install it. */
        @JavascriptInterface
        fun installUpdate() {
            runOnUiThread {
                val pageHost = Uri.parse(webView.url ?: "").host
                val siteHost = Uri.parse(loadedBase ?: "").host
                if (pageHost.isNullOrBlank() || !pageHost.equals(siteHost, ignoreCase = true)) return@runOnUiThread
                android.widget.Toast.makeText(this@MainActivity, "Downloading the update…", android.widget.Toast.LENGTH_SHORT).show()
                lifecycleScope.launch {
                    Updater.downloadAndInstall(this@MainActivity)?.let {
                        android.widget.Toast.makeText(this@MainActivity, it, android.widget.Toast.LENGTH_LONG).show()
                    }
                }
            }
        }

        @JavascriptInterface
        fun linkAccount(token: String?) {
            if (token.isNullOrBlank()) return
            runOnUiThread {
                // Only accept it from our own website, never from another page.
                val pageHost = Uri.parse(webView.url ?: "").host
                val siteHost = Uri.parse(loadedBase ?: "").host
                if (pageHost.isNullOrBlank() || !pageHost.equals(siteHost, ignoreCase = true)) return@runOnUiThread
                if (!Prefs.linkToken(this@MainActivity, token)) return@runOnUiThread
                refreshBanner()
                lifecycleScope.launch {
                    val status = StepReader.status(this@MainActivity)
                    if (status.available && !status.stepsGranted) {
                        // First time on this phone: go straight to "Allow step access".
                        startActivity(Intent(this@MainActivity, SetupActivity::class.java))
                    } else {
                        startLive()
                    }
                }
            }
        }
    }

    /**
     * The strips behind the clock/battery at the top and the gesture bar at the bottom belong
     * to the app, not the website. Paint them the page's own background colour (whatever
     * Light/Dark/Automatic and colour theme the person chose), with dark or light icons to suit.
     */
    private fun matchBarsToPage() {
        val js = "(function(){var b=getComputedStyle(document.body).backgroundColor;" +
            "if(!b||b.indexOf('rgba(0, 0, 0, 0)')===0)b=getComputedStyle(document.documentElement).backgroundColor;" +
            "return b;})()"
        webView.evaluateJavascript(js) { result ->
            val nums = Regex("""\d+(\.\d+)?""").findAll(result ?: "").map { it.value.toDouble() }.toList()
            if (nums.size < 3) return@evaluateJavascript
            if (nums.size >= 4 && nums[3] == 0.0) return@evaluateJavascript     // still transparent
            val (r, g, b) = nums.take(3).map { it.toInt().coerceIn(0, 255) }
            val colour = android.graphics.Color.rgb(r, g, b)
            findViewById<View>(R.id.root).setBackgroundColor(colour)
            window.decorView.setBackgroundColor(colour)
            val lightPage = (0.299 * r + 0.587 * g + 0.114 * b) > 150
            WindowCompat.getInsetsController(window, window.decorView).apply {
                isAppearanceLightStatusBars = lightPage
                isAppearanceLightNavigationBars = lightPage
            }
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
                matchBarsToPage()
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
