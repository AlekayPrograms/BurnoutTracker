Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Drawing;
using System.Runtime.InteropServices;

public class WinCapture {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);
    [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr hWnd, System.Text.StringBuilder lpString, int nMaxCount);
    [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);
    [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr hWnd, IntPtr hdcBlt, uint nFlags);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int Left, Top, Right, Bottom; }

    public static IntPtr FindByTitle(string partial) {
        IntPtr found = IntPtr.Zero;
        EnumWindows(delegate(IntPtr hWnd, IntPtr lParam) {
            if (!IsWindowVisible(hWnd)) return true;
            int len = GetWindowTextLength(hWnd);
            if (len == 0) return true;
            var sb = new System.Text.StringBuilder(len + 1);
            GetWindowText(hWnd, sb, sb.Capacity);
            string title = sb.ToString();
            if (title.Contains(partial)) {
                RECT rc;
                GetWindowRect(hWnd, out rc);
                int w = rc.Right - rc.Left;
                int h = rc.Bottom - rc.Top;
                Console.WriteLine("Found: " + title + " (" + w + "x" + h + ")");
                if (w > 200 && h > 200) {
                    found = hWnd;
                    return false;
                }
            }
            return true;
        }, IntPtr.Zero);
        return found;
    }

    public static void Capture(IntPtr hwnd, string path) {
        ShowWindow(hwnd, 9);
        SetForegroundWindow(hwnd);
        System.Threading.Thread.Sleep(800);

        RECT rc;
        GetWindowRect(hwnd, out rc);
        int w = rc.Right - rc.Left;
        int h = rc.Bottom - rc.Top;

        Bitmap bmp = new Bitmap(w, h);
        Graphics g = Graphics.FromImage(bmp);
        IntPtr hdc = g.GetHdc();
        PrintWindow(hwnd, hdc, 0x2);
        g.ReleaseHdc(hdc);
        bmp.Save(path);
        g.Dispose();
        bmp.Dispose();
        Console.WriteLine("Saved " + w + "x" + h + " to " + path);
    }
}
"@ -ReferencedAssemblies System.Drawing

$hwnd = [WinCapture]::FindByTitle("BurnoutTracker")
if ($hwnd -ne [IntPtr]::Zero) {
    [WinCapture]::Capture($hwnd, "C:\Users\Alex\Downloads\BurnoutTracker\screenshot_session.png")
} else {
    Write-Output "Main window not found"
}
