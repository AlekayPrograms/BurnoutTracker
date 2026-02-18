param([int]$tabX, [string]$outPath)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Clicker {
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int X, int Y);
    [DllImport("user32.dll")] public static extern void mouse_event(int dwFlags, int dx, int dy, int cData, int dwExtraInfo);
    [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT r);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int cmd);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdc, uint flags);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder sb, int max);
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
    [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@

Add-Type -AssemblyName System.Drawing

# Find the big BurnoutTracker window
$found = [IntPtr]::Zero
[Clicker]::EnumWindows({
    param($hWnd, $lp)
    if (-not [Clicker]::IsWindowVisible($hWnd)) { return $true }
    $len = [Clicker]::GetWindowTextLength($hWnd)
    if ($len -eq 0) { return $true }
    $sb = New-Object System.Text.StringBuilder($len + 1)
    [Clicker]::GetWindowText($hWnd, $sb, $sb.Capacity) | Out-Null
    if ($sb.ToString().Contains("BurnoutTracker")) {
        $rc = New-Object Clicker+RECT
        [Clicker]::GetWindowRect($hWnd, [ref]$rc) | Out-Null
        $w = $rc.Right - $rc.Left
        if ($w -gt 200) {
            $script:found = $hWnd
            $script:winRect = $rc
            return $false
        }
    }
    return $true
}, [IntPtr]::Zero) | Out-Null

$hwnd = $script:found
$rc = $script:winRect

[Clicker]::SetForegroundWindow($hwnd)
Start-Sleep -Milliseconds 300

# Click relative to window position
$clickX = $rc.Left + $tabX
$clickY = $rc.Top + 62
[Clicker]::SetCursorPos($clickX, $clickY)
Start-Sleep -Milliseconds 100
[Clicker]::mouse_event(0x02, 0, 0, 0, 0)
[Clicker]::mouse_event(0x04, 0, 0, 0, 0)
Start-Sleep -Milliseconds 1500

# Capture
$w = $rc.Right - $rc.Left
$h = $rc.Bottom - $rc.Top
$bmp = New-Object System.Drawing.Bitmap($w, $h)
$g = [System.Drawing.Graphics]::FromImage($bmp)
$hdc = $g.GetHdc()
[Clicker]::PrintWindow($hwnd, $hdc, 0x2)
$g.ReleaseHdc($hdc)
$bmp.Save($outPath)
$g.Dispose()
$bmp.Dispose()
Write-Output "Captured $outPath"
