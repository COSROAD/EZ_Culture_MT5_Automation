
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json, os, tempfile, hashlib, socket, errno, contextlib

UTC=timezone.utc

def utc_now_iso():
    return datetime.now(UTC).isoformat()

def _pid_alive(pid:int)->bool:
    if pid<=0:
        return False
    if os.name=="nt":
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION=0x1000
            handle=ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,False,pid)
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid,0)
        return True
    except OSError as e:
        return e.errno==errno.EPERM

@dataclass
class LockResult:
    acquired: bool
    state: str
    reason: str
    owner_pid: int|None
    recovered_stale: bool=False

class SingleInstanceLock:
    def __init__(self,lock_dir:str,role:str="SHADOW_RUNTIME",stale_after_seconds:int=300):
        self.lock_dir=Path(lock_dir)
        self.role=role
        self.stale_after_seconds=stale_after_seconds
        self.owner_file=self.lock_dir/"owner.json"
        self.acquired=False

    def _read_owner(self):
        try:
            return json.loads(self.owner_file.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _is_stale(self,owner:dict|None)->tuple[bool,str]:
        if not owner:
            return True,"MISSING_OR_CORRUPT_OWNER"
        pid=int(owner.get("pid") or 0)
        if not _pid_alive(pid):
            return True,"OWNER_PROCESS_NOT_ALIVE"
        ts=owner.get("heartbeat_utc") or owner.get("start_time_utc")
        if not ts:
            return True,"OWNER_TIME_MISSING"
        try:
            dt=datetime.fromisoformat(ts.replace("Z","+00:00"))
            age=(datetime.now(UTC)-dt.astimezone(UTC)).total_seconds()
            if age>self.stale_after_seconds:
                return True,"OWNER_HEARTBEAT_STALE"
        except Exception:
            return True,"OWNER_TIME_INVALID"
        return False,"OWNER_ACTIVE"

    def acquire(self)->LockResult:
        self.lock_dir.parent.mkdir(parents=True,exist_ok=True)
        try:
            self.lock_dir.mkdir()
        except FileExistsError:
            owner=self._read_owner()
            stale,reason=self._is_stale(owner)
            if not stale:
                return LockResult(False,"LOCK_DENIED","PROCESS_DUPLICATE",int(owner.get("pid") or 0),False)
            # stale lock recovery, only after ownership validation
            try:
                for p in self.lock_dir.iterdir():
                    if p.is_file():
                        p.unlink()
                self.lock_dir.rmdir()
                self.lock_dir.mkdir()
            except Exception as e:
                return LockResult(False,"LOCK_DENIED","STALE_LOCK_RECOVERY_FAILED:"+type(e).__name__,None,False)
            recovered=True
        else:
            recovered=False

        owner={
            "role":self.role,
            "pid":os.getpid(),
            "hostname":socket.gethostname(),
            "start_time_utc":utc_now_iso(),
            "heartbeat_utc":utc_now_iso(),
        }
        atomic_write_json(str(self.owner_file),owner)
        self.acquired=True
        return LockResult(True,"LOCK_ACQUIRED","STALE_LOCK_RECOVERED" if recovered else "FIRST_OWNER",os.getpid(),recovered)

    def heartbeat(self):
        if not self.acquired:
            return
        owner=self._read_owner() or {}
        owner["heartbeat_utc"]=utc_now_iso()
        atomic_write_json(str(self.owner_file),owner)

    def release(self):
        if not self.acquired:
            return
        try:
            for p in self.lock_dir.iterdir():
                if p.is_file(): p.unlink()
            self.lock_dir.rmdir()
        except Exception:
            pass
        self.acquired=False

def validate_json_file(path:str)->bool:
    try:
        json.loads(Path(path).read_text(encoding="utf-8"))
        return True
    except Exception:
        return False

def atomic_write_json(path:str,obj:dict):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=p.name+".",suffix=".tmp",dir=str(p.parent));os.close(fd)
    try:
        Path(tmp).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf-8")
        if not validate_json_file(tmp):
            raise ValueError("TEMP_JSON_VALIDATION_FAILED")
        os.replace(tmp,p)
        if not validate_json_file(str(p)):
            raise ValueError("FINAL_JSON_VALIDATION_FAILED")
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)

def safe_atomic_state_write(path:str,obj:dict)->dict:
    p=Path(path)
    previous=None
    if p.exists():
        try:
            previous=json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            previous=None
    try:
        atomic_write_json(path,obj)
        return {"status":"PASS","previous_preserved":previous is not None}
    except Exception as e:
        if previous is not None and not p.exists():
            atomic_write_json(path,previous)
        return {"status":"FAIL","error":type(e).__name__,"previous_state_classification":"REFERENCE_ONLY"}

def decision_fingerprint(decision:dict)->str:
    keys=("market","broker","instrument","direction","entry_permission","add_permission","exit_state","risk_state","conflict_level","final_action","invalidation_condition")
    payload="|".join(str(decision.get(k)) for k in keys)
    return hashlib.sha256(payload.encode()).hexdigest()

def make_decision_id(decision:dict)->str:
    fp=decision_fingerprint(decision)
    market=str(decision.get("market","UNKNOWN"))
    return "SHD_"+market+"_"+fp[:16].upper()

def make_event_id(market:str,event_type:str,event_time_utc:str)->str:
    return "EVT_"+hashlib.sha256(f"{market}|{event_type}|{event_time_utc}".encode()).hexdigest()[:20].upper()

def meaningful_change(prev:dict|None,cur:dict)->bool:
    if prev is None:
        return True
    keys=("direction","entry_permission","add_permission","exit_state","risk_state","conflict_level","invalidation_condition","final_action")
    return any(prev.get(k)!=cur.get(k) for k in keys)

class DuplicateLedger:
    def __init__(self,path:str):
        self.path=Path(path)
        self.data={"decision_fingerprints":[],"event_ids":[]}
        if self.path.exists():
            try:self.data=json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:pass

    def decision_seen(self,decision:dict)->bool:
        return decision_fingerprint(decision) in set(self.data.get("decision_fingerprints",[]))

    def event_seen(self,event_id:str)->bool:
        return event_id in set(self.data.get("event_ids",[]))

    def record_decision(self,decision:dict):
        fp=decision_fingerprint(decision)
        vals=list(dict.fromkeys(self.data.get("decision_fingerprints",[])+[fp]))[-5000:]
        self.data["decision_fingerprints"]=vals
        atomic_write_json(str(self.path),self.data)

    def record_event(self,event_id:str):
        vals=list(dict.fromkeys(self.data.get("event_ids",[])+[event_id]))[-5000:]
        self.data["event_ids"]=vals
        atomic_write_json(str(self.path),self.data)

def prior_state_reference_only(last_state:dict|None,now:datetime,max_age_seconds:int=120)->dict:
    if not last_state or not last_state.get("time_utc"):
        return {"classification":"REFERENCE_ONLY","fresh":False,"reason":"NO_VALID_PREVIOUS_STATE"}
    try:
        dt=datetime.fromisoformat(last_state["time_utc"].replace("Z","+00:00"))
        if dt.tzinfo is None:dt=dt.replace(tzinfo=UTC)
        age=(now.astimezone(UTC)-dt.astimezone(UTC)).total_seconds()
        return {"classification":"REFERENCE_ONLY","fresh":age<=max_age_seconds,"age_seconds":age,"reason":"RECOMPUTE_REQUIRED"}
    except Exception:
        return {"classification":"REFERENCE_ONLY","fresh":False,"reason":"INVALID_TIMESTAMP"}

def heartbeat_payload(pid:int,start_time:str,last_decision_time:str|None,lock_state:str,
                      tick_freshness:str,m1_freshness:str,m5_freshness:str,signal_freshness:str,
                      macro_status:str,broker_status:dict,last_error:str|None,recovery_state:str,
                      market_closed:bool=False)->dict:
    runtime_status="MARKET_CLOSED" if market_closed else ("DEGRADED" if "STALE" in (tick_freshness,m1_freshness,m5_freshness,signal_freshness) else "RUNNING")
    return {
        "RUNTIME_STATUS":runtime_status,
        "PROCESS_ID":pid,
        "START_TIME":start_time,
        "LAST_HEARTBEAT":utc_now_iso(),
        "LAST_DECISION_TIME":last_decision_time,
        "LOCK_STATE":lock_state,
        "TICK_FRESHNESS":tick_freshness,
        "M1_FRESHNESS":m1_freshness,
        "M5_FRESHNESS":m5_freshness,
        "SIGNAL_FRESHNESS":signal_freshness,
        "MACRO_STATUS":macro_status,
        "BROKER_STATUS":broker_status,
        "LAST_ERROR":last_error,
        "RECOVERY_STATE":recovery_state,
    }
