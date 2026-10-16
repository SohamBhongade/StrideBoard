package com.strideboard.app

import android.os.Bundle
import android.view.View
import android.widget.Button
import androidx.activity.ComponentActivity
import androidx.activity.enableEdgeToEdge

/**
 * Privacy screen. Health Connect opens it when someone asks why StrideBoard wants step access
 * (the rationale activity and the Android 14+ activity-alias in the manifest point here).
 */
class PrivacyActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContentView(R.layout.activity_privacy)
        findViewById<View>(R.id.root).padForSystemBars()
        findViewById<Button>(R.id.close_button).setOnClickListener { finish() }
    }
}
