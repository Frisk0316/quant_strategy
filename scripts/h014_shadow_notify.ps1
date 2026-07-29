param([ValidateSet("start", "ok", "fail")][string]$Phase = "start")
# Windows toast for the H-014 shadow scheduled task, so the cmd window is
# identifiable and the user knows not to shut down mid-cycle (ADR-0011 ops).
# ponytail: notification must never break the cycle - all errors swallowed.
$messages = @{
    start = @("H-014 Shadow Cycle 開始", "每日排程任務執行中（約 10 分鐘）。完成通知出現前請勿關機。")
    ok    = @("H-014 Shadow Cycle 完成", "今日 shadow journal 已寫入，可以安全關機。")
    fail  = @("H-014 Shadow Cycle 失敗", "本次 cycle 未完成，詳見 logs\h014_shadow_daily.log。")
}
try {
    $title, $body = $messages[$Phase]
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    $doc = New-Object Windows.Data.Xml.Dom.XmlDocument
    $doc.LoadXml("<toast scenario=`"reminder`"><visual><binding template=`"ToastGeneric`"><text>$title</text><text>$body</text></binding></visual></toast>")
    $appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show(
        [Windows.UI.Notifications.ToastNotification]::new($doc))
} catch {}
