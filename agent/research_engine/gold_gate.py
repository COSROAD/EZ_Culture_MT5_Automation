
from __future__ import annotations
PERSISTENCE_WINDOWS=(30,60,90,120,180,300)
FEATURES=("TICK_PRESSURE_REVERSAL","DOWNSIDE_VELOCITY_DECAY","ACCELERATION_REVERSAL","FAILED_LOW","SPREAD_NORMALIZATION","M1_REVERSAL","SILVER_RELATIVE_STRENGTH")

def persistence_flags(seconds:int)->dict:
    return {f"PERSIST_{w}S":seconds>=w for w in PERSISTENCE_WINDOWS}

def horizon_metrics(reference_price:float,future:list[tuple[int,float]])->dict:
    out={}
    for h in (60,180,300,600,1800,3600):
        vals=[p for sec,p in future if 0<=sec<=h]
        out[f"NEXT_{h//60}M_MFE"]=None if not vals or not reference_price else max((p-reference_price)/reference_price for p in vals)
        out[f"NEXT_{h//60}M_MAE"]=None if not vals or not reference_price else min((p-reference_price)/reference_price for p in vals)
    return out

def discriminate(true_features:dict,false_sets:list[dict])->dict:
    out={}; n=max(1,len(false_sets))
    for f in FEATURES:
        t=bool(true_features.get(f)); fp=sum(1 for x in false_sets if x.get(f))
        out[f]={
            "true_reversal_occurrence":t,
            "false_positive_occurrence_count":fp,
            "false_positive_rate":fp/n,
            "precision_candidate":(1 if t else 0)/max(1,(1 if t else 0)+fp),
            "separation_strength":(1.0 if t else 0.0)-(fp/n),
        }
    return out

def combination_results(true_features:dict,false_sets:list[dict])->dict:
    combos={
        "A":["TICK_PRESSURE_REVERSAL","DOWNSIDE_VELOCITY_DECAY","FAILED_LOW"],
        "B":["TICK_PRESSURE_REVERSAL","SILVER_RELATIVE_STRENGTH","M1_REVERSAL"],
        "C":["FAILED_LOW","M1_REVERSAL","SPREAD_NORMALIZATION"],
        "D":["TICK_PRESSURE_REVERSAL","M1_REVERSAL","SILVER_RELATIVE_STRENGTH"],
    }
    out={}
    for name,fs in combos.items():
        th=all(true_features.get(f,False) for f in fs)
        fp=sum(1 for s in false_sets if all(s.get(f,False) for f in fs))
        out[name]={"features":fs,"true_reversal_match":th,"false_positive_match_count":fp,"candidate_precision":(1 if th else 0)/max(1,(1 if th else 0)+fp)}
    return out

def early_warning_vs_entry(early_mae,entry_mae,lead_seconds):
    return {
        "early_warning_utility":"HIGH" if lead_seconds is not None and lead_seconds>0 else "VERIFY_REQUIRED",
        "entry_signal_utility":"BETTER_THAN_EARLY_WARNING" if early_mae is not None and entry_mae is not None and entry_mae>early_mae else "VERIFY_REQUIRED",
        "early_warning_mae":early_mae,"entry_mae":entry_mae,"lead_seconds":lead_seconds
    }
