<#
.SYNOPSIS
    Launches the Contact Explorer Desktop Application on Windows.
.EXAMPLE
    .\run.ps1
    .\run.ps1 -DatabasePath "C:\my_data\contacts.db"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [string]$DatabasePath
)

$PSScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $PSScriptRoot

if ($DatabasePath) {
    python run.py --db $DatabasePath
} else {
    python run.py
}
