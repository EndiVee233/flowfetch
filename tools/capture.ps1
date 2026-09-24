
param(
  [string]$Out = "shot.png",
  [string]$TitleMatch = "",
  [string]$ProcessName = "",
  [int]$DelayMs = 0
)
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool BringWindowToTop(IntPtr h);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int c);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowTextLength(IntPtr h);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, System.Text.StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int a, out RECT r, int s);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  public delegate bool EnumProc(IntPtr h, IntPtr l);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static IntPtr Find(string title, string procName) {
    IntPtr found = IntPtr.Zero;
    long bestArea = 0;
    EnumWindows(delegate(IntPtr h, IntPtr l) {
      if (!IsWindowVisible(h)) return true;
      if (procName != "") {
        uint pid = 0;
        GetWindowThreadProcessId(h, out pid);
        try { if (System.Diagnostics.Process.GetProcessById((int)pid).ProcessName != procName) return true; }
        catch { return true; }
      }
      if (title != "") {
        int len = GetWindowTextLength(h);
        if (len == 0) return true;
        var sb = new System.Text.StringBuilder(len + 1);
        GetWindowText(h, sb, sb.Capacity);
        if (sb.ToString().IndexOf(title, StringComparison.OrdinalIgnoreCase) < 0) return true;
      }
      RECT rr;
      if (!GetWindowRect(h, out rr)) return true;
      long area = (long)(rr.Right - rr.Left) * (rr.Bottom - rr.Top);
      if (area > bestArea) { bestArea = area; found = h; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
}
"@
if ($DelayMs -gt 0) { Start-Sleep -Milliseconds $DelayMs }
$r = New-Object W+RECT
if ($TitleMatch -ne "" -or $ProcessName -ne "") {
  $h = [W]::Find($TitleMatch, $ProcessName)
  if ($h -eq [IntPtr]::Zero) { Write-Error "window not found"; exit 2 }
  [void][W]::ShowWindow($h, 9)
  for ($i = 0; $i -lt 6; $i++) {
    [void][W]::SetWindowPos($h, [IntPtr]::Zero, 0, 0, 0, 0, 0x0001 -bor 0x0002 -bor 0x0040)
    [void][W]::BringWindowToTop($h)
    [void][W]::SetForegroundWindow($h)
    Start-Sleep -Milliseconds 350
    if ([W]::GetForegroundWindow() -eq $h) { break }
  }
  Start-Sleep -Milliseconds 900
  $ok = [W]::DwmGetWindowAttribute($h, 9, [ref]$r, 16)
  if ((-not $ok) -or (($r.Right - $r.Left) -le 0)) { [void][W]::GetWindowRect($h, [ref]$r) }
} else {
  $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
  $r.Left = $b.Left; $r.Top = $b.Top; $r.Right = $b.Right; $r.Bottom = $b.Bottom
}
$wd = $r.Right - $r.Left
$hg = $r.Bottom - $r.Top
$bmp = New-Object System.Drawing.Bitmap $wd, $hg
$g = [System.Drawing.Graphics]::FromImage($bmp)
$mode = "screen"
if ($h -ne [IntPtr]::Zero) {
  # 让窗口直接把自己画进内存 DC：即使被别的窗口挡住也能拿到正确内容
  $hdc = $g.GetHdc()
  $ok = [W]::PrintWindow($h, $hdc, 2)
  $g.ReleaseHdc($hdc)
  if ($ok) { $mode = "printwindow" }
}
if ($mode -eq "screen") {
  $g.CopyFromScreen($r.Left, $r.Top, 0, 0, $bmp.Size)
}
$bmp.Save($Out, [System.Drawing.Imaging.ImageFormat]::Png)
$g.Dispose(); $bmp.Dispose()
Write-Output ("saved " + $Out + " " + $wd + "x" + $hg + " at " + $r.Left + "," + $r.Top + " via " + $mode)
