# Timeline probe: start the packaged app, poll every second for up to N seconds,
# record window creation and process exit, then report. Offscreen off (real window).
# ASCII-only: Windows PowerShell 5.1 reads .ps1 as ANSI without a UTF-8 BOM.
param(
    [string]$Exe = "V:\ytdlp-E\packaging\dist\YtDlpGui\YtDlpGui.exe",
    [string]$AppData = "V:\ytdlp-E\packaging\_verify\APPDATA",
    [int]$Seconds = 60,
    [switch]$Fresh
)

Add-Type -Namespace W32 -Name W -MemberDefinition @'
public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);
[DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lParam);
[DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint pid);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hWnd, System.Text.StringBuilder text, int max);
[DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr hWnd);
'@

$appDir = Join-Path $AppData "YtDlpGui"
if ($Fresh -and (Test-Path $appDir)) { Remove-Item $appDir -Recurse -Force }

$env:APPDATA = $AppData
$env:LIUGUANG_DEBUG_IMPORT = "1"
Remove-Item Env:\QT_QPA_PLATFORM -ErrorAction SilentlyContinue

$proc = Start-Process -FilePath $Exe -PassThru
$target = [uint32]$proc.Id
Write-Output "started pid=$target at $(Get-Date -Format HH:mm:ss)"

function Get-VisibleTitles([uint32]$want) {
    $script:titles = New-Object System.Collections.ArrayList
    $cb = [W32.W+EnumWindowsProc]{
        param($hWnd, $lParam)
        $wpid = [uint32]0
        [void][W32.W]::GetWindowThreadProcessId($hWnd, [ref]$wpid)
        if ($wpid -eq $want -and [W32.W]::IsWindowVisible($hWnd)) {
            $sb = New-Object System.Text.StringBuilder 512
            [void][W32.W]::GetWindowTextW($hWnd, $sb, 512)
            if ($sb.Length -gt 0) { [void]$script:titles.Add($sb.ToString()) }
        }
        return $true
    }
    [void][W32.W]::EnumWindows($cb, [IntPtr]::Zero)
    return $script:titles
}

for ($i = 1; $i -le $Seconds; $i++) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        Write-Output "EXITED after ${i}s with code $($proc.ExitCode)"
        break
    }
    $t = Get-VisibleTitles $target
    if ($t.Count -gt 0) {
        Write-Output "  t=${i}s windows=$($t.Count) -> $($t -join ' | ')"
    }
    if ($i -eq $Seconds) {
        Write-Output "STILL_ALIVE after ${Seconds}s"
    }
}

if (-not $proc.HasExited) {
    # Send WM_CLOSE to verify the app's normal shutdown path (persists window
    # geometry). Never set QT_QPA_PLATFORM to an empty string: Qt treats "" as
    # an invalid platform name and the window is never created.
    Add-Type -Namespace W32 -Name M -MemberDefinition @'
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string cls, string title);
[DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessageTimeout(IntPtr h, uint msg, IntPtr w, IntPtr l, uint flags, uint timeout, out IntPtr res);
'@
    $short = [char]0x0079 + [char]0x0074 + [char]0x002D + [char]0x0064 + [char]0x006C + [char]0x0070 + " " + `
             [char]0x56FE + [char]0x5F62 + [char]0x7528 + [char]0x6237 + [char]0x754C + [char]0x9762
    $suffix = " - " + $short
    $hwnd = [W32.M]::FindWindow($null, ($short + $suffix))
    if ($hwnd -eq [IntPtr]::Zero) {
        Write-Output "WM_CLOSE: main window not found by title"
    } else {
        $res = [IntPtr]::Zero
        [void][W32.M]::SendMessageTimeout($hwnd, 0x0010, [IntPtr]::Zero, [IntPtr]::Zero, 2, 5000, [ref]$res)
        $deadline = (Get-Date).AddSeconds(20)
        while (-not $proc.HasExited -and (Get-Date) -lt $deadline) { Start-Sleep -Milliseconds 300 }
        if ($proc.HasExited) {
            Write-Output "CLOSE_OK: exited normally with code $($proc.ExitCode)"
        } else {
            Write-Output "CLOSE_TIMEOUT: still alive 20 s after WM_CLOSE"
        }
    }
}
if (-not $proc.HasExited) { $proc.Kill(); Write-Output "killed by probe" }

$boot = Join-Path $appDir "logs\bootstrap.log"
if (Test-Path $boot) {
    Write-Output "--- bootstrap.log ---"
    Get-Content $boot -Encoding UTF8
}
$log = Join-Path $appDir "logs\startup-crash.log"
if (Test-Path $log) {
    Write-Output "--- startup-crash.log (tail) ---"
    Get-Content $log -Encoding UTF8 | Select-Object -Last 25
}
