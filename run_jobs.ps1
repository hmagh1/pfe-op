$basicats = 'FACTU','OPS','IAM','CRM360','M5W','PORTAIL','LOGIS'; 
foreach($b in $basicats){ 
    try { 
        $j = Invoke-RestMethod -Method Post -Uri 'http://127.0.0.1:18000/api/jobs' -ContentType 'application/json' -Body "{`"basicat`":`"$b`"}" -ErrorAction Stop; 
        $id = $j.job_id; 
        $r1 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18000/api/jobs/$id/run-fr" -ErrorAction Stop; 
        $r2 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18000/api/jobs/$id/run-snif/horsprod" -ErrorAction Stop; 
        $r3 = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:18000/api/jobs/$id/run-snif/prod" -ErrorAction Stop; 
        $c1 = if($r1.pending_decisions){$r1.pending_decisions.Count}else{0}; 
        $c2 = if($r2.pending_decisions){$r2.pending_decisions.Count}else{0}; 
        $c3 = if($r3.pending_decisions){$r3.pending_decisions.Count}else{0}; 
        "BASICAT=$b FR=$c1 SNIF_HORS=$c2 SNIF_PROD=$c3 JOB=$id"; 
        if($c1+$c2+$c3 -gt 0){ 
            $target = if($c1 -gt 0){$r1} elseif($c2 -gt 0){$r2} else {$r3}; 
            $target.pending_decisions | Select-Object -First 10 decision_id,env,src_ip,dst_ip,flowMainSG,flowGrefSG,proposed_flux,proposed_nom | Format-Table -AutoSize | Out-String | Write-Output; 
        } 
    } catch { "BASICAT=$b ERROR=$($_.Exception.Message)" } 
}
