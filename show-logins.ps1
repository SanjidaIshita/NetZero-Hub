# Prints the demo login details stored in .env.
Set-Location $PSScriptRoot
$envs = @{}
Get-Content .env | Where-Object { $_ -match '^(DEMO_[A-Z_]+)=(.*)$' } | ForEach-Object { $envs[$matches[1]] = $matches[2] }
Write-Host ""
Write-Host "Sign in at http://localhost:3000" -ForegroundColor Green
Write-Host ("  Resident:  username: resident        password: {0}" -f $envs.DEMO_RESIDENT_PASSWORD)
Write-Host ("  Staff:     username: provider_admin  password: {0}" -f $envs.DEMO_STAFF_PASSWORD)
Write-Host ""
