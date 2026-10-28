package com.strideboard.app

import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Encrypts the phone token before it's saved, with a key kept in the Android Keystore.
 * The key never leaves the phone's secure hardware (where it has one) and can't be copied
 * out of the app, so the saved token is useless to anyone reading the app's files.
 *
 * Saved form: "v1:" + base64(12-byte IV + AES-GCM ciphertext).
 */
object SecretBox {
    private const val KEYSTORE = "AndroidKeyStore"
    private const val ALIAS = "strideboard_token_key"
    private const val PREFIX = "v1:"
    private const val IV_BYTES = 12
    private const val TAG_BITS = 128

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (ks.getKey(ALIAS, null) as? SecretKey)?.let { return it }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE)
        gen.init(
            KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .setKeySize(256)
                .build()
        )
        return gen.generateKey()
    }

    /** Returns the encrypted form, or null if the Keystore isn't working on this phone. */
    fun seal(plain: String): String? = try {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val out = cipher.iv + cipher.doFinal(plain.toByteArray(Charsets.UTF_8))
        PREFIX + Base64.encodeToString(out, Base64.NO_WRAP)
    } catch (e: Exception) {
        null
    }

    /** True for something [seal] made (as opposed to an old, unencrypted token). */
    fun isSealed(saved: String) = saved.startsWith(PREFIX)

    /** The token again, or "" if it can't be read (the phone then just asks to log in again). */
    fun open(saved: String): String = try {
        val bytes = Base64.decode(saved.removePrefix(PREFIX), Base64.NO_WRAP)
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(TAG_BITS, bytes, 0, IV_BYTES))
        String(cipher.doFinal(bytes, IV_BYTES, bytes.size - IV_BYTES), Charsets.UTF_8)
    } catch (e: Exception) {
        ""
    }
}
