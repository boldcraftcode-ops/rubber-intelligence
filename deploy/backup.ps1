# ============================================================
#  OP Margin - backup.ps1
#  Backup harian database (snapshot konsisten lewat SQLite backup API)
#  + folder unggahan (bila ada). Menyimpan 30 hari terakhir.
#  Jadwalkan harian lewat Task Scheduler (lihat deploy/install-windows.md).
#  Restore: lihat deploy/restore.md
# ============================================================

param(
    [string]$FolderBackend = "C:\op-margin\backend",
    [string]$FolderTujuan  = "C:\op-margin-backup",
    [int]$SimpanHari       = 30
)

$ErrorActionPreference = "Stop"
$stempel = Get-Date -Format "yyyy-MM-dd_HHmm"
$tujuan  = Join-Path $FolderTujuan $stempel
New-Item -ItemType Directory -Force -Path $tujuan | Out-Null

$log = Join-Path $FolderTujuan "backup-log.txt"
function Catat($pesan) {
    $baris = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $pesan
    Add-Content -Path $log -Value $baris
    Write-Host $baris
}

try {
    # --- 1. Database: snapshot konsisten (aman walau service sedang menulis)
    $python = Join-Path $FolderBackend ".venv\Scripts\python.exe"
    $dbAsal = Join-Path $FolderBackend "opmargin.db"
    $dbTujuan = Join-Path $tujuan "opmargin.db"
    if (Test-Path $dbAsal) {
        & $python -c "import sqlite3; s=sqlite3.connect(r'$dbAsal'); d=sqlite3.connect(r'$dbTujuan'); s.backup(d); d.close(); s.close()"
        if ($LASTEXITCODE -ne 0) { throw "python sqlite backup gagal" }
        Catat "OK  database -> $dbTujuan ($([math]::Round((Get-Item $dbTujuan).Length/1MB,1)) MB)"
    } else {
        Catat "LEWAT  database tidak ditemukan di $dbAsal"
    }

    # --- 2. File .env TIDAK ikut dibackup ke folder bersama (berisi rahasia).
    #        Simpan salinannya sekali secara manual di tempat aman.

    # --- 3. Folder unggahan (bila dipakai untuk menyimpan file asli unggahan)
    $unggahan = Join-Path $FolderBackend "unggahan"
    if (Test-Path $unggahan) {
        Copy-Item $unggahan (Join-Path $tujuan "unggahan") -Recurse
        Catat "OK  folder unggahan ikut dibackup"
    }

    # --- 4. Verifikasi singkat: file db hasil backup bisa dibuka & utuh
    $cek = & $python -c "import sqlite3; print(sqlite3.connect(r'$dbTujuan').execute('PRAGMA integrity_check').fetchone()[0])"
    if ($cek.Trim() -ne "ok") { throw "integrity_check hasil backup: $cek" }
    Catat "OK  integrity_check = ok"

    # --- 5. Hapus backup lebih tua dari $SimpanHari hari
    Get-ChildItem $FolderTujuan -Directory |
        Where-Object { $_.CreationTime -lt (Get-Date).AddDays(-$SimpanHari) } |
        ForEach-Object {
            Remove-Item $_.FullName -Recurse -Force
            Catat "HAPUS  backup lama $($_.Name)"
        }

    Catat "SELESAI backup $stempel"
    exit 0
}
catch {
    Catat "GAGAL  $($_.Exception.Message)"
    exit 1
}
