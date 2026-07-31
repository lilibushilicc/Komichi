package com.komichi.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Shapes
import androidx.compose.ui.unit.dp

val CgShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),   // 标签
    small = RoundedCornerShape(6.dp),         // 小组件
    medium = RoundedCornerShape(8.dp),       // 卡片/输入框
    large = RoundedCornerShape(12.dp),        // 大卡片
    extraLarge = RoundedCornerShape(16.dp),   // 底部Sheet
)
