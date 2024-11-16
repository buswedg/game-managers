# Requires -RunAsAdministrator

# Stopping Steam
Stop-Process -ProcessName steam -Force

# Define the location of your Steam Library
$SteamLib = 'E:\Steam\steamapps\'

# Define regex pattern to locate the AutoUpdateBehavior token
$myregexAUB = '"AutoUpdateBehavior"\s*"\d+"'

# Get the list of manifest files
$list_of_manifest = Get-ChildItem -Path ($SteamLib + "appmanifest_*.acf")

# Create backups for each manifest file
$list_of_manifest | ForEach-Object { Copy-Item $_.PSPath -Destination ($_.PSPath + ".backup") }

# Function to update AutoUpdateBehavior in manifest files
function Update-AutoUpdateBehavior {
    param (
        [string]$Behavior
    )
    $list_of_manifest | ForEach-Object {
        $content = Get-Content $_.PSPath -Raw
        # Define the replacement pattern
        $replacement = '"AutoUpdateBehavior"		"' + $Behavior + '"'
        $updatedContent = $content -replace $myregexAUB, $replacement
        Set-Content -Path $_.PSPath -Value $updatedContent
    }
}

# User prompt for update behavior selection
Write-Host "Select an update behavior option:"
Write-Host "1: Always keep this game updated (AutoUpdateBehavior 0)"
Write-Host "2: Only update this game when I launch it (AutoUpdateBehavior 1)"
Write-Host "3: High Priority - Always auto-update this game before others (AutoUpdateBehavior 2)"
$choice = Read-Host "Enter the number of your choice"

switch ($choice) {
    '1' { Update-AutoUpdateBehavior "0" }
    '2' { Update-AutoUpdateBehavior "1" }
    '3' { Update-AutoUpdateBehavior "2" }
    default { Write-Host "Invalid choice. Exiting script."; exit 1 }
}

Write-Host "Update completed. Exiting script in 5 seconds."
Start-Sleep -Seconds 5
exit
