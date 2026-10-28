package com.strideboard.app

import android.app.AlertDialog
import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.text.format.DateUtils
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebStorage
import android.widget.Toast
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
 * Setup screen: website address, account status (linked by logging in, no token to paste),
 * step permission, Sync now, last sync result, Open StrideBoard.
 */
class SetupActivity : ComponentActivity() {

    private lateinit var serverInput: EditText
    private lateinit var accountStatus: TextView
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
        accountStatus = findViewById(R.id.account_status)
        hcStatus = findViewById(R.id.hc_status)
        allowButton = findViewById(R.id.allow_button)
        hcSettingsButton = findViewById(R.id.hc_settings_button)
        syncButton = findViewById(R.id.sync_button)
        lastSync = findViewById(R.id.last_sync)

        serverInput.setText(Prefs.serverUrl(this).ifBlank { Prefs.DEFAULT_SERVER })

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
        findViewById<Button>(R.id.disconnect_button).setOnClickListener { confirmDisconnect() }
        findViewById<View>(R.id.privacy_link).setOnClickListener {
            startActivity(Intent(this, PrivacyActivity::class.java))
        }
    }

    /** Stop syncing, give back the Health Connect permission and wipe this phone's copy. */
    private fun confirmDisconnect() {
        AlertDialog.Builder(this)
            .setTitle(R.string.disconnect_title)
            .setMessage(R.string.disconnect_body)
            .setPositiveButton(R.string.disconnect_yes) { _, _ -> lifecycleScope.launch { disconnect() } }
            .setNegativeButton(R.string.consent_not_now, null)
            .show()
    }

    private suspend fun disconnect() {
        if (StepReader.sdkStatus(this) == HealthConnectClient.SDK_AVAILABLE) {
            try {
                HealthConnectClient.getOrCreate(this).permissionController.revokeAllPermissions()
            } catch (e: Exception) {
                // Already gone, or Health Connect busy: the user can still turn it off there.
            }
        }
        SyncScheduler.update(this, backgroundAllowed = false)   // no more background jobs
        Prefs.clearAll(this)                                     // token and sync history
        CookieManager.getInstance().removeAllCookies(null)       // the website login in the app
        WebStorage.getInstance().deleteAllData()
        Toast.makeText(this, R.string.disconnect_done, Toast.LENGTH_LONG).show()
        refreshStatus()
    }

    override fun onResume() {
        super.onResume()
        lifecycleScope.launch { refreshStatus() }
    }

    /** Checks and saves what was typed. Shows a message next to the box if something is wrong. */
    private fun saveInputs(): Boolean {
        val server = Prefs.normalizeServer(serverInput.text.toString())
        if (server == null) {
            serverInput.error = "Type the website address, for example strideboard.pythonanywhere.com"
            serverInput.requestFocus()
            return false
        }
        if (server.startsWith("http://", ignoreCase = true) && !isDebugBuild()) {
            serverInput.error = "This app needs an https:// address"
            serverInput.requestFocus()
            return false
        }
        Prefs.saveSetup(this, server, Prefs.token(this))
        serverInput.setText(server)
        return true
    }

    /**
     * Before Health Connect's own permission window, explain (English and Arabic) what is read,
     * why, and that it's never sold or used for ads. Health Connect is only asked after
     * "Agree & Connect".
     */
    private fun onAllowClicked() {
        when (StepReader.sdkStatus(this)) {
            HealthConnectClient.SDK_AVAILABLE ->
                AlertDialog.Builder(this)
                    .setTitle(R.string.consent_title)
                    .setMessage(getString(R.string.consent_body_en) + "\n\n— — —\n\n" + getString(R.string.consent_body_ar))
                    .setPositiveButton(R.string.consent_agree) { _, _ ->
                        permissionLauncher.launch(StepReader.permissionsToRequest(this))
                    }
                    .setNegativeButton(R.string.consent_not_now, null)
                    .show()
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
        if (!Prefs.isConfigured(this)) {
            lastSync.text = "Log in first: tap \"Open StrideBoard\" and log in. This phone links itself."
            return
        }
        syncButton.isEnabled = false
        lastSync.text = "Syncing…"
        SyncRunner.run(this, inBackground = false, force = true)
        syncButton.isEnabled = true
        refreshStatus()
    }

    private suspend fun refreshStatus() {
        accountStatus.text = if (Prefs.isConfigured(this))
            "Linked ✓ This phone sends steps to the account you logged in with."
        else
            "Not linked yet. Tap \"Open StrideBoard\" below and log in: the app links itself."
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
                    "each time you open the app."
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
