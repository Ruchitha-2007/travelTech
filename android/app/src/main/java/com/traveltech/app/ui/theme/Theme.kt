package com.traveltech.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// TravelTech Color Palette
val CanvasSkyBlue = Color(0xFF7CAEDC)
val CanvasSkyBlueEnd = Color(0xFF95C1E8)
val CardWhite = Color(0xFFFFFFFF)
val ContainerNeutral = Color(0xFFF3F5F8)
val ContainerNeutralAlt = Color(0xFFF8F9FB)

val TextHeadingSlate = Color(0xFF1A1D23)
val TextSecondaryMuted = Color(0xFF6C727F)
val CobaltBluePrimary = Color(0xFF2752E7)
val CobaltBlueDark = Color(0xFF1D4ED8)

// Status Badges & Indicators
val BadgeDangerBg = Color(0xFFFDECEC)
val BadgeDangerText = Color(0xFFD9383A)

val BadgeCautionBg = Color(0xFFFEF3E8)
val BadgeCautionText = Color(0xFFE07832)

val BadgeSafeBg = Color(0xFFECFDF5)
val BadgeSafeText = Color(0xFF16A34A)

val BadgeInfoBg = Color(0xFFEFF6FF)
val BadgeInfoText = Color(0xFF2563EB)

val LightColorScheme = lightColorScheme(
    primary = CobaltBluePrimary,
    onPrimary = Color.White,
    background = CanvasSkyBlue,
    surface = CardWhite,
    onSurface = TextHeadingSlate,
    surfaceVariant = ContainerNeutral,
    onSurfaceVariant = TextSecondaryMuted
)

val TravelTechTypography = Typography(
    headlineLarge = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Bold,
        fontSize = 24.sp,
        color = TextHeadingSlate
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        color = TextHeadingSlate
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        color = TextHeadingSlate
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.Default,
        fontWeight = FontWeight.Medium,
        fontSize = 12.sp,
        color = TextSecondaryMuted
    )
)
