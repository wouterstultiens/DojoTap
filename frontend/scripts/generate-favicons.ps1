$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$publicDir = Join-Path (Get-Location) 'frontend/public'
New-Item -ItemType Directory -Force -Path $publicDir | Out-Null

function New-RoundedRectPath {
    param(
        [float]$X,
        [float]$Y,
        [float]$Width,
        [float]$Height,
        [float]$Radius
    )

    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $diameter = [float]($Radius * 2)

    if ($Radius -le 0) {
        $path.AddRectangle([System.Drawing.RectangleF]::new($X, $Y, $Width, $Height))
        return $path
    }

    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function New-DojoTapBitmap {
    param([int]$Size)

    $bmp = New-Object System.Drawing.Bitmap($Size, $Size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality

    $bgPath = New-RoundedRectPath -X 0 -Y 0 -Width $Size -Height $Size -Radius ($Size * 0.22)
    $grad = New-Object System.Drawing.Drawing2D.LinearGradientBrush(
        [System.Drawing.PointF]::new(0, 0),
        [System.Drawing.PointF]::new($Size, $Size),
        [System.Drawing.Color]::FromArgb(255, 8, 18, 34),
        [System.Drawing.Color]::FromArgb(255, 33, 96, 138)
    )
    $g.FillPath($grad, $bgPath)

    $topGlow = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(58, 112, 160, 225))
    $g.FillEllipse($topGlow, $Size * -0.18, $Size * -0.28, $Size * 0.95, $Size * 0.95)

    $bottomGlow = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(72, 74, 201, 176))
    $g.FillEllipse($bottomGlow, $Size * 0.34, $Size * 0.34, $Size * 0.84, $Size * 0.84)

    $shadowBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(72, 0, 0, 0))
    $mainBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 236, 243, 255))
    $offset = [float]($Size * 0.02)

    foreach ($draw in @(
        @{ Brush = $shadowBrush; Ox = $offset; Oy = $offset },
        @{ Brush = $mainBrush; Ox = 0; Oy = 0 }
    )) {
        $brush = $draw.Brush
        $ox = [float]$draw.Ox
        $oy = [float]$draw.Oy

        $g.FillEllipse($brush, $Size * 0.40 + $ox, $Size * 0.20 + $oy, $Size * 0.20, $Size * 0.20)
        $g.FillEllipse($brush, $Size * 0.34 + $ox, $Size * 0.37 + $oy, $Size * 0.32, $Size * 0.31)
        $g.FillRectangle($brush, $Size * 0.42 + $ox, $Size * 0.50 + $oy, $Size * 0.16, $Size * 0.22)
        $g.FillEllipse($brush, $Size * 0.26 + $ox, $Size * 0.64 + $oy, $Size * 0.48, $Size * 0.19)
        $g.FillRectangle($brush, $Size * 0.30 + $ox, $Size * 0.72 + $oy, $Size * 0.40, $Size * 0.09)
        $g.FillEllipse($brush, $Size * 0.21 + $ox, $Size * 0.77 + $oy, $Size * 0.58, $Size * 0.13)
    }

    $ringPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(255, 74, 201, 176), [Math]::Max(1.5, $Size * 0.045))
    $ringRadius = [float]($Size * 0.115)
    $ringCenterX = [float]($Size * 0.74)
    $ringCenterY = [float]($Size * 0.31)
    $g.DrawEllipse($ringPen, $ringCenterX - $ringRadius, $ringCenterY - $ringRadius, $ringRadius * 2, $ringRadius * 2)

    $tapDotBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 74, 201, 176))
    $tapDotRadius = [float]($Size * 0.048)
    $g.FillEllipse($tapDotBrush, $ringCenterX - $tapDotRadius, $ringCenterY - $tapDotRadius, $tapDotRadius * 2, $tapDotRadius * 2)

    $borderPen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(128, 102, 149, 199), [Math]::Max(1, $Size * 0.02))
    $g.DrawPath($borderPen, $bgPath)

    $borderPen.Dispose()
    $tapDotBrush.Dispose()
    $ringPen.Dispose()
    $mainBrush.Dispose()
    $shadowBrush.Dispose()
    $bottomGlow.Dispose()
    $topGlow.Dispose()
    $grad.Dispose()
    $bgPath.Dispose()
    $g.Dispose()

    return $bmp
}

function Save-DojoTapPng {
    param(
        [int]$Size,
        [string]$Path
    )

    $bmp = New-DojoTapBitmap -Size $Size
    try {
        $bmp.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    }
    finally {
        $bmp.Dispose()
    }
}

Save-DojoTapPng -Size 16 -Path (Join-Path $publicDir 'favicon-16x16.png')
Save-DojoTapPng -Size 32 -Path (Join-Path $publicDir 'favicon-32x32.png')
Save-DojoTapPng -Size 180 -Path (Join-Path $publicDir 'apple-touch-icon.png')
Save-DojoTapPng -Size 192 -Path (Join-Path $publicDir 'android-chrome-192x192.png')
Save-DojoTapPng -Size 512 -Path (Join-Path $publicDir 'android-chrome-512x512.png')

$icoSizes = @(16, 32, 48)
$icoImages = @()
foreach ($size in $icoSizes) {
    $bmp = New-DojoTapBitmap -Size $size
    $ms = New-Object System.IO.MemoryStream
    try {
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $icoImages += [PSCustomObject]@{
            Size = $size
            Bytes = $ms.ToArray()
        }
    }
    finally {
        $ms.Dispose()
        $bmp.Dispose()
    }
}

$icoPath = Join-Path $publicDir 'favicon.ico'
$fs = [System.IO.File]::Open($icoPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write)
$bw = New-Object System.IO.BinaryWriter($fs)
try {
    $bw.Write([UInt16]0)
    $bw.Write([UInt16]1)
    $bw.Write([UInt16]$icoImages.Count)

    $offset = 6 + (16 * $icoImages.Count)
    foreach ($img in $icoImages) {
        $dim = if ($img.Size -ge 256) { [byte]0 } else { [byte]$img.Size }
        $bw.Write([byte]$dim)
        $bw.Write([byte]$dim)
        $bw.Write([byte]0)
        $bw.Write([byte]0)
        $bw.Write([UInt16]1)
        $bw.Write([UInt16]32)
        $bw.Write([UInt32]$img.Bytes.Length)
        $bw.Write([UInt32]$offset)
        $offset += $img.Bytes.Length
    }

    foreach ($img in $icoImages) {
        $bw.Write($img.Bytes)
    }
}
finally {
    $bw.Dispose()
    $fs.Dispose()
}

$svg = @'
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" fill="none">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
      <stop offset="0" stop-color="#081222" />
      <stop offset="1" stop-color="#21608A" />
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#bg)" />
  <circle cx="32" cy="18" r="6.4" fill="#ECF3FF" />
  <ellipse cx="32" cy="31.5" rx="10.2" ry="9.8" fill="#ECF3FF" />
  <rect x="27" y="29.5" width="10" height="17" rx="4" fill="#ECF3FF" />
  <ellipse cx="32" cy="47.5" rx="15" ry="6" fill="#ECF3FF" />
  <rect x="20.5" y="45.5" width="23" height="8" rx="4" fill="#ECF3FF" />
  <ellipse cx="32" cy="54.5" rx="18.5" ry="4.5" fill="#ECF3FF" />
  <circle cx="47.5" cy="19.8" r="6.8" stroke="#4AC9B0" stroke-width="2.8" />
  <circle cx="47.5" cy="19.8" r="2.7" fill="#4AC9B0" />
</svg>
'@
Set-Content -Path (Join-Path $publicDir 'favicon.svg') -Value $svg -Encoding UTF8

$manifest = @'
{
  "name": "DojoTap",
  "short_name": "DojoTap",
  "icons": [
    {
      "src": "/android-chrome-192x192.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/android-chrome-512x512.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ],
  "theme_color": "#0c192b",
  "background_color": "#0c192b",
  "display": "standalone"
}
'@
Set-Content -Path (Join-Path $publicDir 'site.webmanifest') -Value $manifest -Encoding UTF8
