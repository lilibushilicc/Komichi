package com.komichi.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

// Midnight Azure 圆角：更舒展的高级比例
val CgShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),    // 标签 / chip
    small = RoundedCornerShape(8.dp),         // 小组件
    medium = RoundedCornerShape(12.dp),       // 卡片 / 输入框
    large = RoundedCornerShape(16.dp),        // 大卡片
    extraLarge = RoundedCornerShape(28.dp),   // 底部 Sheet（更柔和的展开感）
)
