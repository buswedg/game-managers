#Requires -RunAsAdministrator

$usersKey = Get-ChildItem "Registry::HKEY_USERS"
foreach ($userKey in $usersKey) {
    if ($userKey.PSChildName -ne ".DEFAULT") {
        $path = Join-Path -Path $userKey.PSPath -ChildPath "Software\Microsoft\Windows\CurrentVersion\Uninstall"
        
        try {
            $subkeys = Get-ChildItem -Path $path -ErrorAction Stop
        } catch {
            Write-Host "Uninstall path not found for user: $($userKey.PSChildName)"
            continue
        }

        foreach ($subkey in $subkeys) {
            try {
                $uninstallString = (Get-ItemProperty -Path $subkey.PSPath -ErrorAction Stop).UninstallString

                if ($uninstallString -match "\\Amazon Game Remover.exe") {
                    $choice = Read-Host "Do you want to delete key $($subkey.PSPath)? (Y/N)"
                    if ($choice -eq "Y") {
                        Write-Host "Deleting key $($subkey.PSPath)"
                        Remove-Item -Path $subkey.PSPath -Force -ErrorAction Stop
                    }
                }
            } catch {
                Write-Host "Could not retrieve or process uninstall entry: $($_.Exception.Message)"
            }
        }
    }
}

Write-Host "Exiting script in 5 seconds."; Start-Sleep -Seconds 5
exit
