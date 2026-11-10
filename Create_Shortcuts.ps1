$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$script = Join-Path $root 'Lilith_Download_Desk.pyw'
$pyw = Get-Command pyw.exe -ErrorAction SilentlyContinue
if (-not $pyw) { $pyw = Get-Command pythonw.exe -ErrorAction SilentlyContinue }
if (-not $pyw) { throw 'pyw.exe / pythonw.exe not found. Install Python launcher first.' }
$wsh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = $wsh.CreateShortcut((Join-Path $desktop 'Lilith Download Desk.lnk'))
$shortcut.TargetPath = $pyw.Source
$shortcut.Arguments = ('"{0}"' -f $script)
$shortcut.WorkingDirectory = $root
$shortcut.IconLocation = Join-Path $root 'Lilith.ico'
$shortcut.Description = 'Lilith Download Desk - starts quietly, stays in your system tray'
$shortcut.Save()
Write-Host 'Created desktop shortcut. You can pin it to the Start menu.'
