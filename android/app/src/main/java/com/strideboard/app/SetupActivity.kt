package com.strideboard.app

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.format.DateUtils
import android.view.View
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

/**
 * Setup screen (shown first): website address, token, step permission, Sync now,
 * last sync result, Open StrideBoard.
 */
class SetupActivity : ComponentActivity() {

    private lateinit var serverInput: EditText
    private lateinit var tokenInput: EditText
    private lateinit var hcStatus: TextView
    private lateinit var allowButton: Button
    private lateinit var hcSettingsButton: Button
    private lateinit var syncButton: Button
    private lateinit var lastSync: TextView

    private val permissionLauncher =
        registerForActivityResult(PermissionController.createRequestPermissionResultContract()) { granted ->
            lifecycleScope.launch {
                refreshStatus()
                if (StepReader.STEPS_PERMISSION in granted) {
                    syncNow()
                } else {
                    hcSettingsButton.visibility = View.VISIBLE
                    hcStatus.append(
                        "\n\nIf no permission window appeared, tap \"Open Health Connect\" → " +
                            "App permissions → StrideBoard and turn on Steps."
                    )
                }
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_setup)
        findViewById<View>(R.id.root).padForSystemBars()

        serverInput = findViewById(R.id.server_input)
        tokenInput = findViewById(R.id.token_input)
        hcStatus = findViewById(R.id.hc_status)
        allowButton = findViewById(R.id.allow_button)
        hcSettingsButton = findViewById(R.id.hc_settings_button)
        syncButton = findViewById(R.id.sync_button)
        lastSync = findViewById(R.id.last_sync)

        serverInput.setText(Prefs.serverUrl(this).ifBlank { Prefs.DEFAULT_SERVER })
        tokenInput.setText(Prefs.token(this))

        allowButton.setOnClickListener { onAllowClicked() }
        hcSettingsButton.setOnClickListener { openHealthConnectSettings() }
        syncButton.setOnClickListener {
            if (saveInputs()) lifecycleScope.launch { syncNow() }
        }
        findViewById<Button>(R.id.open_button).setOnClickListener {
            if (saveInputs()) {
                startActivity(
                    Intent(this, MainActivity::class.java)
                        .addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                )
                finish()
            }
        }
        findViewById<View>(R.id.privacy_link).setOnClickListener {
            startActivity(Intent(this, PrivacyActivity::class.java))
        }
    }

    override fun onResume() {
        super.onResume()
        lifecycleScope.launch { refreshStatus() }
    }

    /** Checks and saves what was typed. Shows a message next to the box if something is wrong. */
    private fun saveInputs(): Boolean {
        val server = Prefs.normalizeServer(serverInput.text.toString())
        if (server == null) {
            serverInput.error = "Type the website address, for example sohambhongade.pythonanywhere.com"
            serverInput.requestFocus()
            return false
        }
        if (server.startsWith("http://", ignoreCase = true) && !isDebugBuild()) {
            serverInput.error = "This app needs an https:// address"
            serverInput.requestFocus()
            return false
        }
        val token = tokenInput.text.toString().filterNot { it.isWhitespace() }
        if (token.isEmpty()) {
            tokenInput.error = "Paste your token from Settings on the website"
            tokenInput.requestFocus()
            return false
        }
        Prefs.saveSetup(this, server, token)
        serverInput.setText(server)
        tokenInput.setText(token)
        return true
    }

    private fun onAllowClicked() {
        when (StepReader.sdkStatus(this)) {
            HealthConnectClient.SDK_AVAILABLE ->
                permissionLauncher.launch(StepReader.permissionsToRequest(this))
            HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED -> openPlayStore()
            else -> hcStatus.text = SyncRunner.healthConnectProblem(HealthConnectClient.SDK_UNAVAILABLE)
        }
    }

    private fun openPlayStore() {
        val pkg = StepReader.PROVIDER_PACKAGE
        try {
            startActivity(
                Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$pkg&url=healthconnect%3A%2F%2Fonboarding"))
                    .setPackage("com.android.vending")
                    .putExtra("overlay", true)
                    .putExtra("callerId", packageName)
            )
        } catch (e: ActivityNotFoundException) {
            startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("https://play.google.com/store/apps/details?id=$pkg")))
        }
    }

    private fun openHealthConnectSettings() {
        try {
            startActivity(Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS))
        } catch (e: ActivityNotFoundException) {
            hcStatus.text = "Couldn't open Health Connect. Open it from your phone's Settings → Health Connect."
        }
    }

    private suspend fun syncNow() {
        if (!Prefs.isConfigured(this)) return
        syncButton.isEnabled = false
        lastSync.text = "Syncing…"
        SyncRunner.run(this, inBackground = false)
        syncButton.isEnabled = true
        refreshStatus()
    }

    private suspend fun refreshStatus() {
        val st = StepReader.status(this)
        SyncScheduler.update(this, st.backgroundGranted)

        hcStatus.text = when {
            !st.available -> SyncRunner.healthConnectProblem(st.sdkStatus)
            !st.stepsGranted -> "Step access: not allowed yet."
            st.backgroundGranted ->
                "Step access: allowed ✓\nBackground sync: on (about every 3 hours, plus around 23:30)."
            st.backgroundSupported ->
                "Step access: allowed ✓\nBackground sync: off. Tap \"Allow step access\" again and allow " +
                    "reading data in the background. Until then, steps sync each time you open the app."
            else ->
                "Step access: allowed ✓\nThis phone doesn't support background reading, so steps sync " +
                    "each time you open the app (at most every 15 minutes)."
        }
        allowButton.text = if (st.stepsGranted && (st.backgroundGranted || !st.backgroundSupported))
            "Step access allowed ✓" else "Allow step access"
        if (st.available) hcSettingsButton.visibility = View.VISIBLE

        val attempt = Prefs.lastAttemptAt(this)
        val success = Prefs.lastSuccessAt(this)
        lastSync.text = if (attempt == 0L) {
            "Not synced yet."
        } else {
            val mark = if (Prefs.lastOk(this)) "✓" else "⚠"
            val when_ = if (success == 0L) "never" else DateUtils.getRelativeTimeSpanString(
                success, System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS
            )
            "$mark ${Prefs.lastMessage(this)}\nLast successful sync: $when_"
        }
    }
}
