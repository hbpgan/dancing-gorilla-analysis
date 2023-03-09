from django.views.generic import View
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
import requests
from bsor.Bsor import make_bsor
import os
import math
import io
import sys
from pyquaternion import Quaternion
from urllib.parse import urlparse, parse_qs
from django.shortcuts import render
from .forms import UrlForm

def index(request):
    form = UrlForm()
    return render(request, 'index.html', {'form': form})

def qa(request):
    form = UrlForm()
    return render(request, 'qa.html', {'form': form})

def result(request):
    if request.method == 'GET':
        form = UrlForm(request.GET)
        if form.is_valid():
            url = form.cleaned_data['url']
            analyzed_data = analyze_replay(url)
            return render(request, 'result.html', analyzed_data)
        else:
            return render(request, 'index.html', {'form': form})
            
def registration(request):
  if request.method == "POST":
    data = request.POST
    post_url = 'https://jbsl-web.herokuapp.com/api/dga/post'
    post_data = {
        'dance' : round(float(data['headbanging']), 2),
        'gorilla' : round(float(data['gorilla']), 2),
        'beatleader' : data['score_id'],
        'song_mapper' : data['song_info'],
        'player_name' : data['player_name'],
        'sid' : data['player_id'],
        'token' : settings.JBSL_TOKEN
    }
    
    res = requests.post(post_url,data=post_data)
    
    context = res.json()
    print(res.json())    
    return render(request, 'registration.html', context)

def leaderboard(request):
    if request.method == "GET":   
        jbsl_url = 'https://jbsl-web.herokuapp.com/api/dga'
        res = requests.get(jbsl_url)
        db = res.json()
        #sidのみ抽出
        unique_sid = set([d['sid'] for d in db])
        
        #ゴリラ
        db_gorilla = {}
        sum_d = {}
        for sid in unique_sid:
            r = requests.get(jbsl_url + "?sid=" + sid + "&sort=-gorilla&limit=3")
            db_gorilla[sid] = r.json()
            total = round(sum([d['gorilla'] for d in db_gorilla[sid]]), 2)
            sum_d[sid] = total
            db_gorilla[sid][0]['total'] = total #htmlのloopで参照できるように
        sorted_gorilla = dict(sorted(sum_d.items(), key=lambda x: x[1], reverse=True))
        db_gorilla = {key: db_gorilla[key] for key in sorted_gorilla}
        
        #ダンサー
        db_dance = {}
        sum_d = {}
        for sid in unique_sid:
            r = requests.get(jbsl_url + "?sid=" + sid + "&sort=-dance&limit=3")
            db_dance[sid] = r.json()
            total = round(sum([d['dance'] for d in db_dance[sid]]), 2)
            sum_d[sid] = total
            db_dance[sid][0]['total'] = total #htmlのloopで参照できるように
        sorted_dance = dict(sorted(sum_d.items(), key=lambda x: x[1], reverse=True))
        db_dance = {key: db_dance[key] for key in sorted_dance}
        
        #ぼったち
        db_worldtree = {}
        sum_d = {}
        for sid in unique_sid:
            r = requests.get(jbsl_url + "?sid=" + sid + "&sort=dance&limit=3")
            db_worldtree[sid] = r.json()
            total = round(sum([d['dance'] for d in db_worldtree[sid]]), 2)
            if len(db_worldtree[sid]) < 3:
                total = 999
            sum_d[sid] = total
            db_worldtree[sid][0]['total'] = total #htmlのloopで参照できるように
        sorted_worldtree = dict(sorted(sum_d.items(), key=lambda x: x[1], reverse=False))
        db_worldtree = {key: db_worldtree[key] for key in sorted_worldtree}
        
        #大暴れ度
        db_exiting = {}
        sum_d = {}
        for sid in unique_sid:
            r = requests.get(jbsl_url + "?sid=" + sid)
            d = r.json()
            for i, j in enumerate(d):
                e = float(d[i]['dance'])*2 + float(d[i]['gorilla'])
                d[i]['exiting'] = round(e, 2)
            db_exiting[sid] = sorted(d, key=lambda x: x['gorilla'], reverse=True)
            if len(db_exiting[sid]) > 3:
                db_exiting[sid] = db_exiting[sid][:3]
            total = round(sum(d['exiting'] for d in db_exiting[sid]), 2)
            sum_d[sid] = total
            db_exiting[sid][0]['total'] = total
        sorted_exiting = dict(sorted(sum_d.items(), key=lambda x: x[1], reverse=True))
        db_exiting = {key: db_exiting[key] for key in sorted_exiting}
        
        #辞書型のリストが入った辞書型…
        #db_dance['sid']の[0~2]にトップ3スコアのスコアデータ(辞書型)が入っているということ
        
        context = {}
        context['db_gorilla'] = db_gorilla
        context['db_dance'] = db_dance
        context['db_exiting'] = db_exiting
        context['db_worldtree'] = db_worldtree
        
        return render(request, 'leaderboard.html', context)

def scoreboard(request):
    #全スコアのランキング
    if request.method == "GET":
        jbsl_url = 'https://jbsl-web.herokuapp.com/api/dga'
        context = {}
        
        res = requests.get(jbsl_url+"?sort=-dance&limit100")
        context['dance_scoreboard'] = res.json()
        res = requests.get(jbsl_url+"?sort=-gorilla&limit100")
        context['gorilla_scoreboard'] = res.json()
                
        # 大暴れ度
        res = requests.get(jbsl_url)
        db = res.json()
        i = 0
        for data in db:
            e = float(data['gorilla']) + float(data['dance']) * 2
            db[i]['exiting'] = round(e, 2)
            i += 1
        db.sort(key=lambda d: d['exiting'], reverse=True)
        context['exiting_scoreboard'] = db
        
        #ぼったち
        wtdb = res.json()
        wtdb.sort(key=lambda d: d['dance'], reverse=False)
        if len(wtdb) > 100:
            wtdb = wtdb[:100]
        context['worldtree_scoreboard'] = wtdb
        
        return render(request, 'scoreboard.html', context)

def analyze_replay(webplayer_url):
    parsed = urlparse(webplayer_url)
    query = parse_qs(parsed.query)
    score_id = query["scoreId"][0]
    api_url = 'https://api.beatleader.xyz/score/' + score_id
    r = requests.get(api_url)
    data = r.json()
    bsor_url = data['replay']
    r2 = requests.get(bsor_url)
    f = io.BytesIO(r2.content)

    m = make_bsor(f)
    print('BSOR Version: %d' % m.file_version)
    print('BSOR notes: %d' % len(m.notes))
    print('Song Name (Mapper): {} ({})'.format(m.info.songName, m.info.mapper))
    print('Song Duration: {}sec'.format(round(m.frames[-1].time, 2)))
    print('Song Hash: {}'.format(m.info.songHash))
    print('Song Difficulty: {}'.format(m.info.difficulty))
    print('Game Mode: {}'.format(m.info.mode))
    print('Player Name: {}'.format(m.info.playerName))
    print('Player ID: {}'.format(m.info.playerId))
    print('frames: {}'.format(len(m.frames)))

    total_head_distance = 0.0
    total_right_distance = 0.0
    total_left_distance = 0.0
    total_head_angle = 0.0
    total_right_angle = 0.0
    total_left_angle = 0.0

    print('first note event time: {}'.format(m.notes[0].event_time))
    print('final note event time: {}'.format(m.notes[-1].event_time))

    first_note_frame = 0
    first_note_time = 0.0
    for i in range(len(m.frames)):
        if (m.frames[i].time > m.notes[0].event_time):
            first_note_time = m.frames[i].time
            first_note_frame = i
            break
    final_note_frame = 0
    final_note_time = 0.0
    for i in range(len(m.frames)-1, -1, -1):
        if (m.frames[i].time < m.notes[-1].event_time):
            final_note_time = m.frames[i].time
            final_note_frame = i
            break
    print('{}~{}'.format(first_note_frame, final_note_frame))

    for i in range(first_note_frame, final_note_frame):
        cf = m.frames[i]
        pf = m.frames[i-1]

        hp = (cf.head.x, cf.head.y, cf.head.z)
        prev_hp = (pf.head.x, pf.head.y, pf.head.z)
        hd = math.dist(hp, prev_hp)
        #hd = ((cf.head.x - pf.head.x)**2 + (cf.head.y - pf.head.y)**2 + (cf.head.z - pf.head.z)**2)**0.5
        total_head_distance += hd

        hq1 = Quaternion(cf.head.x_rot, cf.head.y_rot,
                         cf.head.z_rot, cf.head.w_rot)
        hq2 = Quaternion(pf.head.x_rot, pf.head.y_rot,
                         pf.head.z_rot, pf.head.w_rot)
        hq_diff = hq1.inverse * hq2
        hq_deg = abs(hq_diff.degrees)
        total_head_angle += hq_deg

        lp = (cf.left_hand.x, cf.left_hand.y, cf.left_hand.z)
        prev_lp = (pf.left_hand.x, pf.left_hand.y, pf.left_hand.z)
        ld = math.dist(lp, prev_lp)
        total_left_distance += ld

        lq1 = Quaternion(cf.left_hand.x_rot, cf.left_hand.y_rot,
                         cf.left_hand.z_rot, cf.left_hand.w_rot)
        lq2 = Quaternion(pf.left_hand.x_rot, pf.left_hand.y_rot,
                         pf.left_hand.z_rot, pf.left_hand.w_rot)
        lq_diff = lq1.inverse * lq2
        lq_deg = abs(lq_diff.degrees)
        total_left_angle += lq_deg

        rp = (cf.right_hand.x, cf.right_hand.y, cf.right_hand.z)
        prev_rp = (pf.right_hand.x, pf.right_hand.y, pf.right_hand.z)
        rd = math.dist(rp, prev_rp)
        total_right_distance += rd

        rq1 = Quaternion(cf.right_hand.x_rot, cf.right_hand.y_rot,
                         cf.right_hand.z_rot, cf.right_hand.w_rot)
        rq2 = Quaternion(pf.right_hand.x_rot, pf.right_hand.y_rot,
                         pf.right_hand.z_rot, pf.right_hand.w_rot)
        rq_diff = rq1.inverse * rq2
        rq_deg = abs(rq_diff.degrees)
        total_right_angle += rq_deg

    record_duration = final_note_time - first_note_time
    # modifier付きでもnoteのtimeは通常速度の時間で記録されているため処理
    mods = m.info.modifiers.split(',')
    if 'FS' in mods:
        record_duration /= 1.2
    elif 'SF' in mods:
        record_duration /= 1.5
    elif 'SS' in mods:
        record_duration /= 0.85
    print("record duration: {}".format(record_duration))
    nps = len(m.notes) / record_duration
    print('nps: {}'.format(nps))
    hdps = total_head_distance/record_duration
    haps = total_head_angle/record_duration
    ldps = total_left_distance/record_duration
    laps = total_left_angle/record_duration
    rdps = total_right_distance/record_duration
    raps = total_right_angle/record_duration
    print('HMDの移動距離は{}mです。1秒あたり{}mです。'.format(
        round(total_head_distance, 3), round(hdps, 3)))
    print('HMDの回転角度は{}°です。1秒あたり{}°です。'.format(
        round(total_head_angle, 3), round(haps, 3)))
    print('LeftHandの移動距離は{}mです。1秒あたり{}mです。'.format(
        round(total_left_distance, 3), round(ldps, 3)))
    print('LeftHandの回転角度は{}°です。1秒あたり{}°です。'.format(
        round(total_left_angle, 3), round(laps, 3)))
    print('RightHandの移動距離は{}mです。1秒あたり{}mです。'.format(
        round(total_right_distance, 3), round(rdps, 3)))
    print('RightHandの回転角度は{}°です。1秒あたり{}°です。'.format(
        round(total_right_angle, 3), round(raps, 3)))

    headbanging = hdps*100 + haps/3
    print('ダンサー指数は{}です。'.format(round(headbanging,2)))
    total_hand_distance = total_left_distance + total_right_distance
    total_hand_angle = total_left_angle + total_right_angle
    gorilla = (total_hand_distance/record_duration)*10 + ((total_hand_angle/record_duration)/nps)/3
    print('ゴリラ指数は{}です。'.format(round(gorilla,2)))
    
    # わぁいif文、あかりif文大好き
    dancer_rank = ""
    if headbanging > 120:
        dancer_rank = "超ッ！エキサイティンッ！"
    elif headbanging > 100:
        dancer_rank = "超エキサイティング"
    elif headbanging > 80:
        dancer_rank = "エキサイティング"
    elif headbanging > 65:
        dancer_rank = "ダンシング"
    elif headbanging > 55:
        dancer_rank = "かなりノリノリ"
    elif headbanging > 45:
        dancer_rank = "ノリノリ"
    elif headbanging > 35:
        dancer_rank = "ちょっとノリノリ"
    elif headbanging > 30:
        dancer_rank = "ちょっと動く"
    elif headbanging > 25:
        dancer_rank = "あまり動かない"
    elif headbanging > 20:
        dancer_rank = "ぼったち気味"
    elif headbanging > 15:
        dancer_rank = "ぼったち"
    elif headbanging > 11:
        dancer_rank = "超ぼったち"
    elif headbanging > 8:
        dancer_rank = "動かざること山の如し"
    else:
        dancer_rank = "世界樹"
    
    gorilla_rank = ""
    if gorilla > 240:
        gorilla_rank = "ゴッドゴリラ"
    elif gorilla > 210:
        gorilla_rank = "超大暴れゴリラ"
    elif gorilla > 190:
        gorilla_rank = "大暴れゴリラ"
    elif gorilla > 180:
        gorilla_rank = "暴れゴリラ"
    elif gorilla > 170:
        gorilla_rank = "ゴリラ"
    elif gorilla > 160:
        gorilla_rank = "ゴリラジェダイ"
    elif gorilla > 130:
        gorilla_rank = "ジェダイ"
    elif gorilla > 110:
        gorilla_rank = "穏やかジェダイ"
    else:
        gorilla_rank = "まったりジェダイ"
    
    analyzed_data = locals()
    return(analyzed_data)