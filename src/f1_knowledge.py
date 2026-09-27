"""
F1 Knowledge — pure constants and reference strings.
No logic. Imported by engineer.py to inject into the system prompt
and to drive tyre temperature / wear / ERS threshold decisions.
"""

TYRE_OPTIMAL_TEMPS = {
    'C1':    {'min': 90,  'optimal': 100, 'max': 115},
    'C2':    {'min': 85,  'optimal': 95,  'max': 115},
    'C3':    {'min': 80,  'optimal': 90,  'max': 105},
    'C4':    {'min': 75,  'optimal': 85,  'max': 100},
    'C5':    {'min': 70,  'optimal': 80,  'max': 90},
    'C6':    {'min': 65,  'optimal': 75,  'max': 85},
    'Inter': {'min': 60,  'optimal': 70,  'max': 80},
    'Wet':   {'min': 50,  'optimal': 60,  'max': 70},
}

TYRE_WEAR_THRESHOLDS = {
    'manage':    40,   # Start protecting this tyre
    'warning':   60,   # Performance dropping noticeably
    'critical':  75,   # Box very soon
    'emergency': 85,   # Box immediately
}

ERS_THRESHOLDS = {
    'deploy_attack':   70,   # Enough to deploy for overtake attempt
    'deploy_defend':   50,   # Enough to defend one straight
    'harvest_needed':  25,   # Need to start harvesting
    'critical_low':    15,   # Must harvest immediately
}

DRS_ATTACK_WINDOW_SECONDS = 1.0    # Within 1 second to have DRS
DRS_DEFEND_WARNING_SECONDS = 1.2   # Car behind within 1.2s, warn driver

F1_KNOWLEDGE = '''
ERS (Energy Recovery System):
- ERS store holds up to 4 megajoules of energy
- Deploy modes: none (harvesting), medium (balanced), hotlap (maximum qualifying), overtake (maximum attack)
- ERS harvests energy under braking and coasting
- Full deployment gives approximately 160bhp boost for around 33 seconds per lap
- Best deployment zones are long straights and DRS zones
- Harvesting is most effective through slow corners and braking zones
- In F1 25, ERS is recalibrated for more strategic harvesting at high speeds

DRS (Drag Reduction System):
- Available when within 1 second of car ahead at detection point
- Reduces drag on the straight by opening rear wing flap
- Gives approximately 10-15 km/h top speed advantage on straights
- Race control enables DRS after lap 2 of a race
- Disabled under safety car and VSC

Tyres:
- Each compound has an optimal temperature window for maximum grip
- Below optimal: understeer, reduced grip, excess wear from sliding
- Above optimal: grip falls away, blistering risk, rapid wear
- In F1 25, rapid steering inputs cause overheating and faster wear
- Rear tyres typically heat faster than fronts in F1 25
- Higher tyre pressures run cooler but give less mechanical grip
- Tyre wear affects both grip levels and pace — above 40% wear pace starts to drop

Strategy concepts:
- Undercut: pit earlier than rival, use fresh tyre pace to overtake when they pit
- Overcut: stay out longer, build gap while rival is in pits, emerge ahead
- Safety car window: pit under safety car to gain free stop with minimal time loss
- VSC (Virtual Safety Car): slower than full SC, less time saving from pitting
- Free air: no traffic within 2-3 seconds — allows driver to push at full pace
- Dirty air: following within 1-2 seconds reduces downforce and increases tyre wear

Pit stop strategy in F1 25:
- The game calculates ideal and latest pit laps automatically
- Pit stop itself takes approximately 2.5 seconds of stationary time plus pit lane delta
- Undercut typically requires 1.5-2 second pace advantage from fresh tyres
- Two-stop strategy is mandatory at Monaco
- Safety car neutralises pit lane time loss — always consider pitting under SC

Trail braking:
- Continuing to brake while turning into a corner
- Increases corner entry speed and rotation
- Research shows trail braking duration is the top predictor of lap time improvement
- More effective trail braking into slow corners and hairpins gives biggest time gains

Oversteer management:
- Research shows reducing oversteer is one of the biggest performance gains available
- Smooth steering inputs reduce oversteer — sudden flicking movements cause instability
- In F1 25, aggressive driving overheats tyres and causes faster wear

Where time is typically lost:
- Lane deviation from ideal line costs significant time — staying on the optimal line matters most
- Corner exit speed is more important than corner entry speed on most circuits
- Throttle pickup after slow corners is a major differentiator between fast and slow drivers
- Braking too early costs time — trail braking later into corners is faster
'''
