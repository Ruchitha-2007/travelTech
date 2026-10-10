package com.traveltech.app.util

import android.content.Context
import org.json.JSONObject
import java.io.InputStreamReader

object TranslationManager {

    private val cache = mutableMapOf<String, Map<String, String>>()

    fun loadTranslations(context: Context, lang: String): Map<String, String> {
        if (cache.containsKey(lang)) {
            return cache[lang]!!
        }

        val filename = "$lang.json"
        val map = mutableMapOf<String, String>()
        try {
            context.assets.open(filename).use { stream ->
                val reader = InputStreamReader(stream)
                val jsonStr = reader.readText()
                val jsonObj = JSONObject(jsonStr)
                val keys = jsonObj.keys()
                while (keys.hasNext()) {
                    val key = keys.next()
                    map[key] = jsonObj.getString(key)
                }
            }
        } catch (e: Exception) {
            // Fallback to English if file not found
            if (lang != "en") {
                return loadTranslations(context, "en")
            }
        }

        cache[lang] = map
        return map
    }

    fun render(context: Context, key: String, params: Map<String, String> = emptyMap(), lang: String = "en"): String {
        val map = loadTranslations(context, lang)
        var template = map[key] ?: run {
            val enMap = loadTranslations(context, "en")
            enMap[key] ?: key
        }

        for ((k, v) in params) {
            template = template.replace("{$k}", v)
        }
        return template
    }
}
