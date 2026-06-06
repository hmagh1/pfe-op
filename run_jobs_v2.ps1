$base='http://127.0.0.1:18000/api'
$basicats = @('FACTU','OPS','IAM','CRM360','M5W','PORTAIL','LOGIS');
foreach($b in $basicats){
  try {
    $job = Invoke-RestMethod -Method Post -Uri "$base/jobs" -ContentType 'application/json' -Body ("{`"basicat`":`"$b`"}");
    $id = $job.job_id;
    $fr = Invoke-RestMethod -Method Post -Uri ("$base/jobs/$id/run-fr");
    $p1 = $fr.pending_decisions.Count;
    $sn1 = Invoke-RestMethod -Method Post -Uri ("$base/jobs/$id/run-snif/horsprod");
    $p2 = $sn1.pending_decisions.Count;
    $sn2 = Invoke-RestMethod -Method Post -Uri ("$base/jobs/$id/run-snif/prod");
    $p3 = $sn2.pending_decisions.Count;
    Write-Output ("BASICAT=$b FR=$p1 SNIF_HORS=$p2 SNIF_PROD=$p3 JOB=$id");
    if($p3 -gt 0){
      $sn2.pending_decisions | Select-Object -First 10 decision_id,env,src_ip,dst_ip,flowMainSG,flowGrefSG,proposed_flux,proposed_nom | Format-Table -AutoSize;
      break;
    }
  } catch {
    Write-Output ("BASICAT=$b ERROR=$($_.Exception.Message)");
  }
}
