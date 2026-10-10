package com.traveltech.app

import android.app.Application
import dagger.hilt.android.HiltAndroidApp
import org.osmdroid.config.Configuration
import java.io.File

@HiltAndroidApp
class TravelTechApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // Initialize osmdroid configuration
        Configuration.getInstance().userAgentValue = packageName
        val basePath = File(cacheDir, "osmdroid")
        Configuration.getInstance().osmdroidBasePath = basePath
        Configuration.getInstance().osmdroidTileCache = File(basePath, "tiles")
    }
}
