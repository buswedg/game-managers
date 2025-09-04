#Requires -RunAsAdministrator
param(
    [switch]$y
)

$keysFound = 0
$keysDeleted = 0
$keysSkipped = 0
$usersProcessed = 0

$usersKey = Get-ChildItem "Registry::HKEY_USERS"
foreach ($userKey in $usersKey) {
    if ($userKey.PSChildName -ne ".DEFAULT") {
        $usersProcessed++
        $path = Join-Path -Path $userKey.PSPath -ChildPath "Software\Microsoft\Windows\CurrentVersion\Uninstall"
        
        try {
            $subkeys = Get-ChildItem -Path $path -ErrorAction Stop
        } catch {
            Write-Host "Uninstall path not found for user: $($userKey.PSChildName)" -ForegroundColor DarkGray
            continue
        }
        
        foreach ($subkey in $subkeys) {
            try {
                $uninstallString = (Get-ItemProperty -Path $subkey.PSPath -ErrorAction Stop).UninstallString
                if ($uninstallString -match "\\Amazon Game Remover.exe") {
                    $keysFound++
                    
                    if ($y) {
                        Write-Host "Auto-deleting key $($subkey.PSPath)" -ForegroundColor Yellow
                        Remove-Item -Path $subkey.PSPath -Force -ErrorAction Stop
                        $keysDeleted++
                    } else {
                        $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
                        if ($choice -eq "Y") {
                            Write-Host "Deleting key $($subkey.PSPath)" -ForegroundColor Green
                            Remove-Item -Path $subkey.PSPath -Force -ErrorAction Stop
                            $keysDeleted++
                        } else {
                            Write-Host "Skipped key $($subkey.PSPath)" -ForegroundColor Gray
                            $keysSkipped++
                        }
                    }
                }
            } catch {
                Write-Host "Could not retrieve or process uninstall entry: $($_.Exception.Message)" -ForegroundColor Red
            }
        }
    }
}

Write-Host "`nSummary:" -ForegroundColor Cyan
Write-Host "  Users processed: $usersProcessed" -ForegroundColor White
Write-Host "  Amazon registry keys found: $keysFound" -ForegroundColor White
Write-Host "  Amazon registry keys deleted: $keysDeleted" -ForegroundColor White
if ($keysSkipped -gt 0) {
    Write-Host "  Amazon registry keys skipped: $keysSkipped" -ForegroundColor White
}

if ($keysFound -eq 0) {
    Write-Host "No Amazon Game Remover registry keys found." -ForegroundColor Green
}

Write-Host "Exiting script in 5 seconds..." -ForegroundColor Yellow
Start-Sleep -Seconds 5
exit
