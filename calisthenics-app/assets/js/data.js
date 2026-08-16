/* ============================================================================
 * Cali100 — Database esercizi + skill tree
 * Tutti i dati sono statici e restano nel dispositivo. Nessuna rete richiesta.
 *
 * Campi esercizio:
 *   id       identificatore univoco
 *   name     nome in italiano
 *   cat      categoria: warmup | mobility | push | pull | legs | core | skill
 *   muscles  gruppi muscolari coinvolti
 *   diff     difficoltà 1..10
 *   type     reps (ripetizioni) | hold (isometrico, secondi) | cardio (a tempo)
 *   equip    none | elevato (sedia/tavolo/rialzo) | sbarra | muro
 *   rep      [min,max] ripetizioni consigliate (per type reps)
 *   hold     [min,max] secondi di tenuta (per type hold)
 *   dur      [min,max] secondi di lavoro (per type cardio)
 *   reg      id della regressione (variante più facile) — opzionale
 *   prog     id della progressione (variante più difficile) — opzionale
 *   floorAlt id di alternativa senza sbarra — opzionale
 *   uni      true se unilaterale (le ripetizioni sono per lato)
 *   cues     indicazioni tecniche
 *   errori   errori comuni
 *   desc     descrizione sintetica
 * ==========================================================================*/
(function (CALI) {
  'use strict';

  const E = [
    /* ---------------------------------------------------------------- WARM-UP */
    { id:'spot_jog', name:'Corsa sul posto', cat:'warmup', muscles:['Cardio','Gambe'], diff:1, type:'cardio', equip:'none', dur:[30,60],
      cues:['Appoggio morbido sull\'avampiede','Respira in modo regolare'], errori:['Spalle rigide'], desc:'Attivazione cardiovascolare generale per alzare la temperatura corporea.' },
    { id:'jumping_jacks', name:'Jumping jack', cat:'warmup', muscles:['Cardio','Spalle','Gambe'], diff:1, type:'cardio', equip:'none', dur:[30,45],
      cues:['Salti aprendo gambe e braccia insieme','Atterra piegando le ginocchia'], errori:['Ginocchia rigide all\'atterraggio'], desc:'Salto con apertura simultanea di braccia e gambe: riscalda tutto il corpo.' },
    { id:'high_knees', name:'Ginocchia alte', cat:'warmup', muscles:['Cardio','Core','Flessori anca'], diff:2, type:'cardio', equip:'none', dur:[30,45],
      cues:['Porta le ginocchia all\'altezza dell\'anca','Busto eretto'], errori:['Inclinarsi indietro'], desc:'Corsa sul posto portando le ginocchia in alto: attiva core e flessori dell\'anca.' },
    { id:'butt_kicks', name:'Calciata dietro', cat:'warmup', muscles:['Cardio','Femorali'], diff:1, type:'cardio', equip:'none', dur:[30,45],
      cues:['Talloni verso i glutei','Ritmo costante'], errori:['Busto in avanti'], desc:'Corsa sul posto portando i talloni ai glutei: scalda i femorali.' },
    { id:'arm_circles', name:'Circonduzioni braccia', cat:'warmup', muscles:['Spalle'], diff:1, type:'cardio', equip:'none', dur:[20,30],
      cues:['Cerchi ampi e controllati','Metà avanti, metà indietro'], errori:['Movimento troppo rapido'], desc:'Cerchi con le braccia tese per mobilitare e riscaldare le spalle.' },
    { id:'leg_swings', name:'Slanci gamba', cat:'warmup', muscles:['Anche','Femorali'], diff:1, type:'cardio', equip:'none', uni:true, dur:[20,30],
      cues:['Oscilla la gamba avanti/indietro','Tieni il busto stabile'], errori:['Compensare con la schiena'], desc:'Slanci controllati della gamba per aprire l\'anca. Alterna i lati.' },
    { id:'hip_circles', name:'Circonduzioni anche', cat:'warmup', muscles:['Anche','Core'], diff:1, type:'cardio', equip:'none', dur:[20,30],
      cues:['Mani sui fianchi','Disegna cerchi ampi con il bacino'], errori:['Muovere solo le spalle'], desc:'Rotazioni del bacino per mobilitare le anche.' },
    { id:'torso_twists', name:'Torsioni busto', cat:'warmup', muscles:['Core','Colonna'], diff:1, type:'cardio', equip:'none', dur:[20,30],
      cues:['Ruota da bacino fermo','Braccia rilassate che seguono'], errori:['Strappi bruschi'], desc:'Torsioni del tronco per mobilitare la colonna dorsale.' },
    { id:'inchworm', name:'Inchworm (bruco)', cat:'warmup', muscles:['Core','Femorali','Spalle'], diff:2, type:'reps', equip:'none', rep:[5,8],
      cues:['Cammina con le mani fino al plank','Poi cammina con i piedi verso le mani'], errori:['Bacino che cede in plank'], desc:'Dalla posizione eretta cammini con le mani in plank e torni: scalda tutta la catena.' },
    { id:'scap_pushup', name:'Scapular push-up', cat:'warmup', muscles:['Spalle','Dorsali','Core'], diff:2, type:'reps', equip:'none', rep:[8,12], prog:'wall_walk',
      cues:['In plank alto avvicina/allontana le scapole','Braccia sempre tese'], errori:['Piegare i gomiti'], desc:'Protrazione e retrazione delle scapole in plank: attiva la cintura scapolare.' },
    { id:'cat_cow', name:'Cat-cow (gatto)', cat:'warmup', muscles:['Colonna','Core'], diff:1, type:'reps', equip:'none', rep:[8,10],
      cues:['Inarca ed incurva la schiena lentamente','Sincronizza col respiro'], errori:['Movimento solo di collo'], desc:'Mobilità della colonna a quattro appoggi tra flessione ed estensione.' },
    { id:'wrist_prep', name:'Mobilità polsi', cat:'warmup', muscles:['Polsi','Avambracci'], diff:1, type:'cardio', equip:'none', dur:[30,40],
      cues:['Carica delicatamente il peso su mani a terra','Ruota in tutte le direzioni'], errori:['Forzare il dolore'], desc:'Preparazione dei polsi indispensabile prima di plank, push-up e verticali.' },
    { id:'deep_squat_hold', name:'Squat profondo (tenuta)', cat:'warmup', muscles:['Anche','Caviglie','Adduttori'], diff:2, type:'hold', equip:'none', hold:[20,40],
      cues:['Scendi in accosciata completa','Gomiti spingono le ginocchia in fuori'], errori:['Talloni che si alzano'], desc:'Tenuta in accosciata profonda per aprire anche e caviglie.' },
    { id:'ankle_rocks', name:'Mobilità caviglie', cat:'warmup', muscles:['Caviglie','Polpacci'], diff:1, type:'cardio', equip:'none', uni:true, dur:[20,30],
      cues:['Ginocchio oltre le dita del piede','Tallone a terra'], errori:['Sollevare il tallone'], desc:'Dondolii del ginocchio in avanti per la dorsiflessione della caviglia.' },
    { id:'shoulder_swings', name:'Slanci spalle', cat:'warmup', muscles:['Spalle','Petto'], diff:1, type:'cardio', equip:'none', dur:[20,30],
      cues:['Apri e chiudi le braccia in orizzontale','Ampiezza progressiva'], errori:['Movimento a scatti'], desc:'Aperture e chiusure delle braccia per scaldare petto e spalle.' },

    /* --------------------------------------------------------------- MOBILITY / DEFATICAMENTO */
    { id:'child_pose', name:'Posizione del bambino', cat:'mobility', muscles:['Colonna','Dorsali','Spalle'], diff:1, type:'hold', equip:'none', hold:[30,60],
      cues:['Glutei verso i talloni','Braccia lunghe in avanti'], errori:['Trattenere il respiro'], desc:'Allungamento di schiena e spalle a fine seduta.' },
    { id:'cobra_stretch', name:'Allungamento cobra', cat:'mobility', muscles:['Addome','Flessori anca'], diff:1, type:'hold', equip:'none', hold:[20,40],
      cues:['Spingi il petto in alto','Spalle basse, lontane dalle orecchie'], errori:['Contrarre i glutei'], desc:'Estensione dolce della colonna per allungare l\'addome.' },
    { id:'hamstring_stretch', name:'Allungamento femorali', cat:'mobility', muscles:['Femorali'], diff:1, type:'hold', equip:'none', hold:[30,45],
      cues:['Schiena lunga','Piega dall\'anca verso i piedi'], errori:['Arrotondare la schiena'], desc:'Allungamento della catena posteriore delle gambe.' },
    { id:'quad_stretch', name:'Allungamento quadricipiti', cat:'mobility', muscles:['Quadricipiti','Flessori anca'], diff:1, type:'hold', equip:'none', uni:true, hold:[25,40],
      cues:['Tallone verso il gluteo','Ginocchia vicine'], errori:['Inarcare la schiena'], desc:'Allungamento del quadricipite in piedi. Alterna i lati.' },
    { id:'chest_doorway', name:'Allungamento petto (stipite)', cat:'mobility', muscles:['Petto','Spalle'], diff:1, type:'hold', equip:'elevato', hold:[25,40],
      cues:['Avambraccio sullo stipite','Ruota dolcemente il busto'], errori:['Spingere troppo'], desc:'Apertura del petto usando uno stipite o un angolo.' },
    { id:'pigeon_stretch', name:'Allungamento del piccione', cat:'mobility', muscles:['Glutei','Anche'], diff:2, type:'hold', equip:'none', uni:true, hold:[30,45],
      cues:['Stinco avanti, gamba dietro tesa','Busto rilassato in avanti'], errori:['Forzare il ginocchio'], desc:'Allungamento profondo di glutei e rotatori dell\'anca. Alterna i lati.' },
    { id:'shoulder_stretch', name:'Allungamento spalle', cat:'mobility', muscles:['Spalle','Dorsali'], diff:1, type:'hold', equip:'none', uni:true, hold:[20,30],
      cues:['Porta il braccio davanti al petto','Tira dolcemente con l\'altro braccio'], errori:['Alzare la spalla'], desc:'Allungamento del deltoide posteriore. Alterna i lati.' },
    { id:'calf_stretch', name:'Allungamento polpacci', cat:'mobility', muscles:['Polpacci'], diff:1, type:'hold', equip:'elevato', uni:true, hold:[25,40],
      cues:['Tallone a terra, gamba tesa','Spingi il bacino avanti'], errori:['Sollevare il tallone'], desc:'Allungamento del polpaccio contro il muro. Alterna i lati.' },
    { id:'seated_twist', name:'Torsione da seduto', cat:'mobility', muscles:['Colonna','Glutei'], diff:1, type:'hold', equip:'none', uni:true, hold:[25,35],
      cues:['Schiena dritta','Ruota verso il ginocchio piegato'], errori:['Curvare la schiena'], desc:'Torsione della colonna da seduto. Alterna i lati.' },

    /* ------------------------------------------------------------------- PUSH */
    { id:'wall_pushup', name:'Piegamenti al muro', cat:'push', muscles:['Petto','Tricipiti','Spalle'], diff:1, type:'reps', equip:'muro', rep:[10,20], prog:'incline_pushup',
      cues:['Corpo in linea retta','Gomiti a circa 45°'], errori:['Sederino all\'indietro'], desc:'Piegamenti in piedi contro il muro: primo passo per costruire la spinta.' },
    { id:'incline_pushup', name:'Piegamenti inclinati', cat:'push', muscles:['Petto','Tricipiti','Spalle'], diff:2, type:'reps', equip:'elevato', rep:[8,15], reg:'wall_pushup', prog:'knee_pushup',
      cues:['Mani su tavolo/sedia stabile','Corpo teso dalla testa ai talloni'], errori:['Bacino alto'], desc:'Piegamenti con le mani su un rialzo: più facili dei piegamenti a terra.' },
    { id:'knee_pushup', name:'Piegamenti sulle ginocchia', cat:'push', muscles:['Petto','Tricipiti','Core'], diff:3, type:'reps', equip:'none', rep:[8,15], reg:'incline_pushup', prog:'pushup',
      cues:['Linea retta da ginocchia a testa','Petto verso il pavimento'], errori:['Bacino che cede'], desc:'Versione facilitata dei piegamenti con appoggio sulle ginocchia.' },
    { id:'negative_pushup', name:'Piegamenti negativi', cat:'push', muscles:['Petto','Tricipiti','Core'], diff:3, type:'reps', equip:'none', rep:[5,8], reg:'knee_pushup', prog:'pushup',
      cues:['Scendi in 3-5 secondi','Risali dalle ginocchia'], errori:['Scendere di colpo'], desc:'Solo la fase di discesa lenta: costruisce forza verso il primo piegamento completo.' },
    { id:'pushup', name:'Piegamenti (push-up)', cat:'push', muscles:['Petto','Tricipiti','Spalle','Core'], diff:4, type:'reps', equip:'none', rep:[8,15], reg:'knee_pushup', prog:'diamond_pushup',
      cues:['Corpo rigido come una tavola','Gomiti a ~45°, petto sfiora terra'], errori:['Gomiti troppo larghi','Collo in avanti'], desc:'Il piegamento classico a corpo teso: fondamentale della spinta orizzontale.' },
    { id:'wide_pushup', name:'Piegamenti presa larga', cat:'push', muscles:['Petto','Spalle'], diff:4, type:'reps', equip:'none', rep:[8,14], reg:'pushup', prog:'archer_pushup',
      cues:['Mani più larghe delle spalle','Petto in mezzo alle mani'], errori:['Spalle alle orecchie'], desc:'Piegamenti a presa larga per enfatizzare il petto.' },
    { id:'diamond_pushup', name:'Piegamenti diamante', cat:'push', muscles:['Tricipiti','Petto'], diff:5, type:'reps', equip:'none', rep:[6,12], reg:'pushup', prog:'archer_pushup',
      cues:['Indici e pollici a formare un rombo','Gomiti stretti al corpo'], errori:['Gomiti che si aprono'], desc:'Piegamenti con mani unite sotto il petto: grande stimolo per i tricipiti.' },
    { id:'decline_pushup', name:'Piegamenti declinati', cat:'push', muscles:['Petto alto','Spalle','Tricipiti'], diff:5, type:'reps', equip:'elevato', rep:[8,12], reg:'pushup', prog:'pike_pushup',
      cues:['Piedi su un rialzo','Corpo in linea'], errori:['Bacino che cede'], desc:'Piegamenti con i piedi rialzati: più carico su spalle e petto alto.' },
    { id:'archer_pushup', name:'Piegamenti dell\'arciere', cat:'push', muscles:['Petto','Tricipiti','Core'], diff:6, type:'reps', equip:'none', uni:true, rep:[4,8], reg:'diamond_pushup', prog:'pseudo_planche_pushup',
      cues:['Un braccio lavora, l\'altro resta teso di lato','Scendi verso la mano che spinge'], errori:['Ruotare il bacino'], desc:'Piegamenti asimmetrici: tappa verso il piegamento a un braccio. Ripetizioni per lato.' },
    { id:'pike_pushup', name:'Pike push-up', cat:'push', muscles:['Spalle','Tricipiti'], diff:5, type:'reps', equip:'none', rep:[6,12], reg:'decline_pushup', prog:'elevated_pike_pushup',
      cues:['Bacino alto a "V rovesciata"','Testa verso terra tra le mani'], errori:['Gomiti larghi'], desc:'Piegamento a V per spostare il carico sulle spalle: base per la verticale.' },
    { id:'elevated_pike_pushup', name:'Pike push-up rialzato', cat:'push', muscles:['Spalle','Tricipiti'], diff:6, type:'reps', equip:'elevato', rep:[5,10], reg:'pike_pushup', prog:'wall_hspu',
      cues:['Piedi su un rialzo, busto più verticale','Testa sfiora terra'], errori:['Perdere l\'allineamento'], desc:'Pike push-up con piedi rialzati: avvicina l\'angolo alla verticale.' },
    { id:'pseudo_planche_pushup', name:'Pseudo planche push-up', cat:'push', muscles:['Spalle','Petto','Core'], diff:7, type:'reps', equip:'none', rep:[5,10], reg:'archer_pushup', prog:'wall_hspu',
      cues:['Mani all\'altezza del bacino, dita verso i piedi','Spalle avanti oltre le mani'], errori:['Bacino che cede'], desc:'Piegamenti inclinati in avanti: costruiscono la forza specifica per la planche.' },
    { id:'bench_dip', name:'Dip sulla sedia', cat:'push', muscles:['Tricipiti','Spalle','Petto'], diff:3, type:'reps', equip:'elevato', rep:[8,15], prog:'parallel_dip',
      cues:['Mani sul bordo della sedia','Gomiti indietro, non larghi'], errori:['Spalle in su'], desc:'Dip con appoggio dietro su una sedia: ottimo per i tricipiti a casa.' },
    { id:'parallel_dip', name:'Dip alle parallele', cat:'push', muscles:['Petto','Tricipiti','Spalle'], diff:6, type:'reps', equip:'elevato', rep:[5,12], reg:'bench_dip', prog:'wall_hspu',
      cues:['Corpo leggermente inclinato avanti','Scendi finché le spalle sono sotto i gomiti'], errori:['Scendere troppo se dolore'], desc:'Dip tra due superfici stabili (sedie robuste): grande esercizio di spinta.' },
    { id:'explosive_pushup', name:'Piegamenti esplosivi', cat:'push', muscles:['Petto','Tricipiti','Spalle'], diff:7, type:'reps', equip:'none', rep:[4,8], reg:'pushup', prog:'wall_hspu',
      cues:['Spingi con forza per staccare le mani','Atterraggio morbido'], errori:['Perdere la rigidità del corpo'], desc:'Piegamenti con spinta esplosiva (anche a battito di mani): potenza per la parte alta.' },
    { id:'wall_hspu', name:'Verticale al muro spinta', cat:'push', muscles:['Spalle','Tricipiti','Core'], diff:8, type:'reps', equip:'muro', rep:[3,8], reg:'elevated_pike_pushup', prog:'freestanding_handstand',
      cues:['In verticale al muro, scendi con la testa a terra','Spingi fino a braccia tese'], errori:['Inarcare la schiena'], desc:'Piegamenti in verticale contro il muro: massima spinta verticale.' },

    /* ------------------------------------------------------------------- PULL */
    { id:'prone_ytw', name:'Y-T-W a terra', cat:'pull', muscles:['Dorsali bassi','Trapezio','Spalle post.'], diff:2, type:'reps', equip:'none', rep:[8,12], prog:'superman_hold',
      cues:['Prono, solleva le braccia a Y, T e W','Scapole che si avvicinano'], errori:['Alzare il mento'], desc:'Sollevamenti delle braccia da prono per la salute delle spalle e la schiena alta.' },
    { id:'superman_hold', name:'Superman', cat:'pull', muscles:['Erettori','Glutei','Spalle post.'], diff:2, type:'hold', equip:'none', hold:[20,40], reg:'prone_ytw', prog:'table_row',
      cues:['Solleva braccia e gambe da prono','Sguardo a terra'], errori:['Iperestendere il collo'], desc:'Tenuta a corpo inarcato per la catena posteriore.' },
    { id:'table_row', name:'Rematore australiano (tavolo)', cat:'pull', muscles:['Dorsali','Bicipiti','Spalle post.'], diff:4, type:'reps', equip:'elevato', rep:[6,12], reg:'superman_hold', prog:'inverted_row_bar', floorAlt:'towel_row',
      cues:['Sotto un tavolo robusto, corpo teso','Tira il petto verso il bordo'], errori:['Bacino che cede'], desc:'Trazione orizzontale afferrando il bordo di un tavolo solido: alternativa senza sbarra.' },
    { id:'towel_row', name:'Rematore con asciugamano (porta)', cat:'pull', muscles:['Dorsali','Bicipiti'], diff:3, type:'reps', equip:'elevato', rep:[8,15], prog:'table_row',
      cues:['Asciugamano attorno a una maniglia robusta','Tira il corpo verso la porta'], errori:['Usare solo le braccia'], desc:'Trazione tenendo un asciugamano su una maniglia solida: rematore senza attrezzi.' },
    { id:'inverted_row_bar', name:'Rematore orizzontale (sbarra bassa)', cat:'pull', muscles:['Dorsali','Bicipiti','Core'], diff:4, type:'reps', equip:'sbarra', rep:[6,12], reg:'table_row', prog:'negative_pullup', floorAlt:'table_row',
      cues:['Corpo teso sotto la sbarra bassa','Scapole indietro, petto alla barra'], errori:['Bacino basso'], desc:'Trazione orizzontale sotto una sbarra bassa. Senza sbarra usa il rematore al tavolo.' },
    { id:'dead_hang', name:'Sospensione alla sbarra', cat:'pull', muscles:['Presa','Dorsali','Spalle'], diff:3, type:'hold', equip:'sbarra', hold:[20,45], prog:'scapular_pull', floorAlt:'towel_row',
      cues:['Appeso a braccia tese','Spalle attive, non "molli"'], errori:['Spalle completamente rilassate'], desc:'Rimanere appesi alla sbarra: costruisce presa e prepara le trazioni.' },
    { id:'scapular_pull', name:'Scapular pull (trazioni scapolari)', cat:'pull', muscles:['Dorsali','Trapezio'], diff:4, type:'reps', equip:'sbarra', rep:[6,12], reg:'dead_hang', prog:'negative_pullup', floorAlt:'table_row',
      cues:['Appeso, abbassa le spalle senza piegare i gomiti','Piccolo movimento controllato'], errori:['Piegare i gomiti'], desc:'Attivazione delle scapole appesi alla sbarra: il primo controllo per le trazioni.' },
    { id:'negative_pullup', name:'Trazioni negative', cat:'pull', muscles:['Dorsali','Bicipiti'], diff:5, type:'reps', equip:'sbarra', rep:[3,6], reg:'scapular_pull', prog:'assisted_pullup', floorAlt:'table_row',
      cues:['Parti col mento sopra la barra','Scendi in 3-5 secondi'], errori:['Scendere di colpo'], desc:'Solo la discesa lenta della trazione: la via maestra al primo pull-up.' },
    { id:'assisted_pullup', name:'Trazioni assistite', cat:'pull', muscles:['Dorsali','Bicipiti'], diff:5, type:'reps', equip:'sbarra', rep:[4,8], reg:'negative_pullup', prog:'pullup', floorAlt:'table_row',
      cues:['Un piede su una sedia per aiutare','Tira soprattutto con la schiena'], errori:['Spingere troppo con la gamba'], desc:'Trazioni con appoggio parziale del piede per ridurre il carico.' },
    { id:'pullup', name:'Trazioni (pull-up)', cat:'pull', muscles:['Dorsali','Bicipiti','Core'], diff:6, type:'reps', equip:'sbarra', rep:[4,10], reg:'assisted_pullup', prog:'wide_pullup', floorAlt:'table_row',
      cues:['Presa prona, mento sopra la barra','Scapole indietro e in basso'], errori:['Slancio con le gambe','Mezze ripetizioni'], desc:'La trazione classica a presa prona: regina della trazione verticale.' },
    { id:'chinup', name:'Trazioni presa supina (chin-up)', cat:'pull', muscles:['Bicipiti','Dorsali'], diff:6, type:'reps', equip:'sbarra', rep:[4,10], reg:'assisted_pullup', prog:'archer_pullup', floorAlt:'table_row',
      cues:['Palmi verso di te','Petto verso la barra'], errori:['Range incompleto'], desc:'Trazione a presa supina: più bicipiti, spesso più accessibile del pull-up.' },
    { id:'wide_pullup', name:'Trazioni presa larga', cat:'pull', muscles:['Dorsali','Spalle post.'], diff:7, type:'reps', equip:'sbarra', rep:[3,8], reg:'pullup', prog:'archer_pullup', floorAlt:'table_row',
      cues:['Presa oltre le spalle','Porta il petto alla barra'], errori:['Ridurre il range'], desc:'Trazioni a presa larga per enfatizzare la larghezza del dorso.' },
    { id:'archer_pullup', name:'Trazioni dell\'arciere', cat:'pull', muscles:['Dorsali','Bicipiti'], diff:8, type:'reps', equip:'sbarra', uni:true, rep:[2,5], reg:'wide_pullup', prog:'high_pullup', floorAlt:'table_row',
      cues:['Tira su un lato, l\'altro braccio resta teso','Alterna i lati'], errori:['Non completare la salita'], desc:'Trazioni asimmetriche verso la trazione a un braccio. Ripetizioni per lato.' },
    { id:'high_pullup', name:'Trazioni esplosive alte', cat:'pull', muscles:['Dorsali','Bicipiti','Potenza'], diff:8, type:'reps', equip:'sbarra', rep:[2,5], reg:'wide_pullup', prog:'muscleup',
      cues:['Tira esplosivo portando il petto/lo sterno alla barra','Corpo compatto'], errori:['Slancio disordinato'], desc:'Trazioni potenti che portano il petto alla barra: preparazione al muscle-up.' },

    /* ------------------------------------------------------------------- LEGS */
    { id:'glute_bridge', name:'Ponte per i glutei', cat:'legs', muscles:['Glutei','Femorali'], diff:1, type:'reps', equip:'none', rep:[12,20], prog:'single_leg_glute_bridge',
      cues:['Spingi coi talloni','Stringi i glutei in alto'], errori:['Iperestendere la schiena'], desc:'Sollevamento del bacino da supino: attiva e rinforza i glutei.' },
    { id:'single_leg_glute_bridge', name:'Ponte a una gamba', cat:'legs', muscles:['Glutei','Femorali','Core'], diff:3, type:'reps', equip:'none', uni:true, rep:[8,15], reg:'glute_bridge', prog:'sliding_leg_curl',
      cues:['Una gamba tesa in aria','Bacino livellato'], errori:['Anca che si abbassa'], desc:'Ponte glutei su una gamba sola. Ripetizioni per lato.' },
    { id:'squat', name:'Squat a corpo libero', cat:'legs', muscles:['Quadricipiti','Glutei'], diff:2, type:'reps', equip:'none', rep:[12,25], prog:'split_squat',
      cues:['Scendi con il petto alto','Ginocchia in linea con le punte'], errori:['Talloni che si alzano','Ginocchia in dentro'], desc:'Lo squat fondamentale: piega anche e ginocchia mantenendo la schiena neutra.' },
    { id:'sumo_squat', name:'Squat sumo', cat:'legs', muscles:['Adduttori','Glutei','Quadricipiti'], diff:2, type:'reps', equip:'none', rep:[12,20], reg:'squat', prog:'cossack_squat',
      cues:['Piedi larghi, punte in fuori','Scendi tra i talloni'], errori:['Ginocchia in dentro'], desc:'Squat a base larga per interno coscia e glutei.' },
    { id:'wall_sit', name:'Wall sit (sedia al muro)', cat:'legs', muscles:['Quadricipiti','Glutei'], diff:2, type:'hold', equip:'muro', hold:[30,60], prog:'squat_jump',
      cues:['Schiena al muro, cosce parallele al suolo','Ginocchia a 90°'], errori:['Scivolare troppo in basso'], desc:'Tenuta isometrica seduti contro il muro: resistenza dei quadricipiti.' },
    { id:'step_up', name:'Salita su rialzo (step-up)', cat:'legs', muscles:['Quadricipiti','Glutei'], diff:2, type:'reps', equip:'elevato', uni:true, rep:[8,15], prog:'split_squat',
      cues:['Sali spingendo con il tallone sul rialzo','Controlla la discesa'], errori:['Spingersi con la gamba a terra'], desc:'Salite su una sedia/rialzo stabile. Ripetizioni per lato.' },
    { id:'split_squat', name:'Affondo statico (split squat)', cat:'legs', muscles:['Quadricipiti','Glutei'], diff:3, type:'reps', equip:'none', uni:true, rep:[8,15], reg:'squat', prog:'reverse_lunge',
      cues:['Passo lungo, scendi in verticale','Ginocchio dietro verso terra'], errori:['Busto in avanti'], desc:'Affondo sul posto: forza monopodalica di base. Ripetizioni per lato.' },
    { id:'reverse_lunge', name:'Affondo indietro', cat:'legs', muscles:['Quadricipiti','Glutei','Core'], diff:3, type:'reps', equip:'none', uni:true, rep:[8,14], reg:'split_squat', prog:'bulgarian_split_squat',
      cues:['Passo indietro e scendi','Spingi col tallone avanti per risalire'], errori:['Sbilanciarsi'], desc:'Affondo facendo un passo all\'indietro: più stabile per le ginocchia. Per lato.' },
    { id:'bulgarian_split_squat', name:'Affondo bulgaro', cat:'legs', muscles:['Quadricipiti','Glutei'], diff:5, type:'reps', equip:'elevato', uni:true, rep:[6,12], reg:'reverse_lunge', prog:'assisted_pistol',
      cues:['Piede dietro su un rialzo','Scendi in verticale sul piede avanti'], errori:['Passo troppo corto'], desc:'Affondo con piede posteriore rialzato: enorme stimolo monopodalico. Per lato.' },
    { id:'cossack_squat', name:'Squat cosacco', cat:'legs', muscles:['Adduttori','Quadricipiti','Anche'], diff:5, type:'reps', equip:'none', uni:true, rep:[6,10], reg:'sumo_squat', prog:'assisted_pistol',
      cues:['Scendi su una gamba, l\'altra tesa di lato','Tallone a terra'], errori:['Curvare la schiena'], desc:'Affondo laterale profondo per mobilità e forza dell\'anca. Per lato.' },
    { id:'squat_jump', name:'Squat con salto', cat:'legs', muscles:['Quadricipiti','Glutei','Potenza'], diff:5, type:'reps', equip:'none', rep:[8,15], reg:'squat', prog:'broad_jump',
      cues:['Esplodi verso l\'alto','Atterra morbido piegando le ginocchia'], errori:['Atterraggio rigido'], desc:'Squat pliometrico per potenza ed esplosività delle gambe.' },
    { id:'broad_jump', name:'Salto in lungo da fermo', cat:'legs', muscles:['Glutei','Quadricipiti','Potenza'], diff:5, type:'reps', equip:'none', rep:[5,10], reg:'squat_jump',
      cues:['Carica indietro le braccia','Salta avanti e atterra stabile'], errori:['Atterrare sbilanciato'], desc:'Salto orizzontale massimale per potenza esplosiva.' },
    { id:'calf_raise', name:'Sollevamenti sui polpacci', cat:'legs', muscles:['Polpacci'], diff:1, type:'reps', equip:'none', rep:[15,25], prog:'single_calf_raise',
      cues:['Sali sulle punte al massimo','Discesa lenta'], errori:['Rimbalzare'], desc:'Sollevamento sulle punte dei piedi per i polpacci.' },
    { id:'single_calf_raise', name:'Polpaccio a una gamba', cat:'legs', muscles:['Polpacci'], diff:3, type:'reps', equip:'none', uni:true, rep:[10,20], reg:'calf_raise',
      cues:['Su una gamba, salita completa','Usa un dito al muro per l\'equilibrio'], errori:['Range ridotto'], desc:'Sollevamento del polpaccio su una gamba. Per lato.' },
    { id:'sliding_leg_curl', name:'Leg curl scivolato', cat:'legs', muscles:['Femorali','Glutei'], diff:5, type:'reps', equip:'none', rep:[6,12], reg:'single_leg_glute_bridge', prog:'nordic_curl_negative',
      cues:['Talloni su calzini/panno su pavimento liscio','Bacino alto, allunga e ripiega le gambe'], errori:['Bacino che cade'], desc:'Curl per i femorali facendo scivolare i talloni: catena posteriore senza attrezzi.' },
    { id:'nordic_curl_negative', name:'Nordic curl negativo', cat:'legs', muscles:['Femorali'], diff:7, type:'reps', equip:'elevato', rep:[3,6], reg:'sliding_leg_curl',
      cues:['Caviglie bloccate sotto un appoggio','Scendi in avanti frenando coi femorali'], errori:['Cadere senza frenare'], desc:'Discesa controllata in ginocchio con caviglie bloccate: uno dei più duri per i femorali.' },
    { id:'assisted_pistol', name:'Pistol squat assistito', cat:'legs', muscles:['Quadricipiti','Glutei','Core'], diff:6, type:'reps', equip:'elevato', uni:true, rep:[4,8], reg:'bulgarian_split_squat', prog:'box_pistol',
      cues:['Tieniti a un supporto o siediti su una sedia','Una gamba tesa avanti'], errori:['Tallone che si alza'], desc:'Squat su una gamba con appoggio/supporto. Per lato.' },
    { id:'box_pistol', name:'Pistol su rialzo (box pistol)', cat:'legs', muscles:['Quadricipiti','Glutei','Core'], diff:7, type:'reps', equip:'elevato', uni:true, rep:[3,6], reg:'assisted_pistol', prog:'pistol_squat',
      cues:['Siediti brevemente su un rialzo e risali','Gamba libera tesa avanti'], errori:['Rimbalzare sul rialzo'], desc:'Pistol squat scendendo fino a un rialzo: riduce il range fino a padroneggiarlo. Per lato.' },
    { id:'pistol_squat', name:'Pistol squat', cat:'legs', muscles:['Quadricipiti','Glutei','Core','Equilibrio'], diff:8, type:'reps', equip:'none', uni:true, rep:[2,6], reg:'box_pistol', prog:'shrimp_squat',
      cues:['Scendi completo su una gamba','Gamba libera tesa avanti, tallone a terra'], errori:['Perdere l\'equilibrio','Tallone sollevato'], desc:'Accosciata completa su una gamba sola: forza, mobilità ed equilibrio. Per lato.' },
    { id:'shrimp_squat', name:'Shrimp squat', cat:'legs', muscles:['Quadricipiti','Glutei','Core'], diff:8, type:'reps', equip:'none', uni:true, rep:[2,5], reg:'pistol_squat',
      cues:['Trattieni la caviglia dietro','Scendi finché il ginocchio sfiora terra'], errori:['Cadere in avanti'], desc:'Accosciata monopodalica con gamba posteriore piegata: alternativa avanzata al pistol. Per lato.' },

    /* ------------------------------------------------------------------- CORE */
    { id:'dead_bug', name:'Dead bug', cat:'core', muscles:['Core profondo','Addome'], diff:1, type:'reps', equip:'none', rep:[8,14], prog:'bird_dog',
      cues:['Zona lombare a contatto col suolo','Estendi braccio e gamba opposti'], errori:['Schiena che si inarca'], desc:'Da supino estendi braccio e gamba opposti: controllo del core senza carico sulla schiena.' },
    { id:'bird_dog', name:'Bird dog', cat:'core', muscles:['Core','Erettori','Glutei'], diff:1, type:'reps', equip:'none', uni:true, rep:[8,12], reg:'dead_bug', prog:'plank',
      cues:['A quattro appoggi estendi braccio e gamba opposti','Bacino fermo'], errori:['Ruotare il bacino'], desc:'Estensione alternata di braccio e gamba a quattro appoggi per la stabilità. Per lato.' },
    { id:'plank', name:'Plank', cat:'core', muscles:['Addome','Core','Spalle'], diff:2, type:'hold', equip:'none', hold:[30,60], reg:'bird_dog', prog:'hollow_hold',
      cues:['Corpo in linea retta','Contrai addome e glutei'], errori:['Bacino alto o cadente'], desc:'Tenuta sugli avambracci a corpo teso: il fondamentale della stabilità del core.' },
    { id:'side_plank', name:'Plank laterale', cat:'core', muscles:['Obliqui','Core'], diff:3, type:'hold', equip:'none', uni:true, hold:[20,45], reg:'plank', prog:'hollow_hold',
      cues:['Corpo in linea su un avambraccio','Anca alta'], errori:['Bacino che scende'], desc:'Plank sul fianco per gli obliqui. Per lato.' },
    { id:'superman_core', name:'Nuotata a terra', cat:'core', muscles:['Erettori','Glutei'], diff:2, type:'reps', equip:'none', rep:[10,16], prog:'hollow_hold',
      cues:['Prono, alterna braccio e gamba opposti in su','Movimento fluido'], errori:['Strappi bruschi'], desc:'Da prono solleva alternando braccia e gambe: rinforza la bassa schiena.' },
    { id:'mountain_climbers', name:'Mountain climber', cat:'core', muscles:['Core','Cardio','Spalle'], diff:3, type:'cardio', equip:'none', dur:[25,45], prog:'hollow_rock',
      cues:['In plank alto porta le ginocchia al petto','Bacino basso e stabile'], errori:['Sederino che sale'], desc:'Corsa orizzontale in plank: core e cardio insieme.' },
    { id:'lying_leg_raise', name:'Sollevamento gambe da terra', cat:'core', muscles:['Addome basso','Flessori anca'], diff:3, type:'reps', equip:'none', rep:[8,15], prog:'reverse_crunch',
      cues:['Gambe tese salgono a 90°','Lombare a contatto col suolo'], errori:['Schiena che si stacca'], desc:'Sollevamento delle gambe da supino per l\'addome basso.' },
    { id:'reverse_crunch', name:'Crunch inverso', cat:'core', muscles:['Addome basso'], diff:3, type:'reps', equip:'none', rep:[10,16], reg:'lying_leg_raise', prog:'hanging_knee_raise',
      cues:['Porta le ginocchia al petto sollevando il bacino','Controlla la discesa'], errori:['Usare lo slancio'], desc:'Arrotolamento del bacino verso il petto: addome basso senza slanci.' },
    { id:'bicycle_crunch', name:'Crunch bicicletta', cat:'core', muscles:['Obliqui','Addome'], diff:3, type:'reps', equip:'none', rep:[12,20], prog:'v_up',
      cues:['Gomito verso il ginocchio opposto','Gambe che pedalano lente'], errori:['Tirare il collo'], desc:'Crunch con rotazione alternata per gli obliqui.' },
    { id:'russian_twist', name:'Russian twist', cat:'core', muscles:['Obliqui','Core'], diff:3, type:'reps', equip:'none', rep:[12,24], prog:'v_up',
      cues:['Busto inclinato indietro','Ruota toccando ai lati'], errori:['Muovere solo le braccia'], desc:'Torsioni da seduto per gli obliqui.' },
    { id:'flutter_kicks', name:'Flutter kicks', cat:'core', muscles:['Addome basso','Flessori anca'], diff:3, type:'cardio', equip:'none', dur:[20,40], prog:'hollow_hold',
      cues:['Gambe tese battono su e giù','Lombare a terra'], errori:['Schiena inarcata'], desc:'Battute alternate delle gambe da supino: addome basso e resistenza.' },
    { id:'plank_shoulder_tap', name:'Plank con tocco spalla', cat:'core', muscles:['Core','Spalle','Anti-rotazione'], diff:3, type:'reps', equip:'none', rep:[10,20], reg:'plank', prog:'hollow_rock',
      cues:['In plank alto tocca la spalla opposta','Bacino fermo, niente rotazioni'], errori:['Oscillare i fianchi'], desc:'Plank alto toccando le spalle: forza anti-rotazione del core.' },
    { id:'hollow_hold', name:'Hollow hold (scafo)', cat:'core', muscles:['Addome','Core'], diff:4, type:'hold', equip:'none', hold:[15,40], reg:'plank', prog:'hollow_rock',
      cues:['Lombare schiacciata a terra','Braccia e gambe tese e basse'], errori:['Schiena che si inarca'], desc:'Posizione a "scafo" da supino: cardine del controllo del core in tutta la calistenia.' },
    { id:'hollow_rock', name:'Hollow rock', cat:'core', muscles:['Addome','Core'], diff:5, type:'reps', equip:'none', rep:[10,20], reg:'hollow_hold', prog:'v_up',
      cues:['Mantieni lo scafo e dondola avanti/indietro','Corpo rigido come un dondolo'], errori:['Perdere la posizione hollow'], desc:'Oscillazione mantenendo la posizione hollow: forza e controllo dinamico.' },
    { id:'v_up', name:'V-up', cat:'core', muscles:['Addome','Flessori anca'], diff:5, type:'reps', equip:'none', rep:[8,15], reg:'hollow_rock', prog:'tuck_lsit',
      cues:['Solleva insieme busto e gambe a "V"','Tocca i piedi con le mani'], errori:['Slancio scoordinato'], desc:'Chiusura simultanea di busto e gambe a forma di V.' },
    { id:'hanging_knee_raise', name:'Ginocchia al petto alla sbarra', cat:'core', muscles:['Addome basso','Presa'], diff:4, type:'reps', equip:'sbarra', rep:[6,12], prog:'hanging_leg_raise', floorAlt:'reverse_crunch',
      cues:['Appeso, porta le ginocchia al petto','Niente slancio'], errori:['Dondolare'], desc:'Sollevamento delle ginocchia appesi alla sbarra. Senza sbarra usa il crunch inverso.' },
    { id:'hanging_leg_raise', name:'Gambe tese alla sbarra', cat:'core', muscles:['Addome','Flessori anca','Presa'], diff:6, type:'reps', equip:'sbarra', rep:[5,10], reg:'hanging_knee_raise', prog:'toes_to_bar', floorAlt:'lying_leg_raise',
      cues:['Gambe tese fino all\'orizzontale o oltre','Bacino che si arrotola'], errori:['Usare lo slancio'], desc:'Sollevamento a gambe tese appesi alla sbarra. Senza sbarra usa il sollevamento gambe a terra.' },
    { id:'toes_to_bar', name:'Toes to bar', cat:'core', muscles:['Addome','Dorsali','Presa'], diff:7, type:'reps', equip:'sbarra', rep:[3,8], reg:'hanging_leg_raise', floorAlt:'v_up',
      cues:['Porta le punte dei piedi alla sbarra','Compatta tutto il corpo'], errori:['Dondolio eccessivo'], desc:'Le punte dei piedi salgono a toccare la sbarra: grande forza dell\'addome. Senza sbarra usa i V-up.' },
    { id:'tuck_lsit', name:'L-sit raccolto (tuck)', cat:'core', muscles:['Addome','Flessori anca','Tricipiti'], diff:5, type:'hold', equip:'elevato', hold:[10,25], reg:'hollow_hold', prog:'lsit',
      cues:['Mani su due rialzi, solleva il corpo','Ginocchia raccolte al petto'], errori:['Spalle in su'], desc:'L-sit con ginocchia raccolte, mani su due rialzi: base per l\'L-sit completo.' },
    { id:'lsit', name:'L-sit', cat:'core', muscles:['Addome','Flessori anca','Tricipiti'], diff:7, type:'hold', equip:'elevato', hold:[8,20], reg:'tuck_lsit',
      cues:['Gambe tese e parallele al suolo','Spalle depresse, braccia tese'], errori:['Gambe piegate','Spalle in su'], desc:'Sospensione a "L" con gambe tese: forza di addome e spalle da fermo.' },
    { id:'dragon_flag_negative', name:'Dragon flag negativo', cat:'core', muscles:['Addome','Core','Erettori'], diff:7, type:'reps', equip:'elevato', rep:[3,6], reg:'hollow_rock', prog:'dragon_flag',
      cues:['Afferra un appoggio dietro la testa','Scendi lentamente col corpo dritto'], errori:['Piegare i fianchi'], desc:'Discesa lenta del corpo teso (stile Bruce Lee): controllo estremo del core.' },
    { id:'dragon_flag', name:'Dragon flag', cat:'core', muscles:['Addome','Core','Erettori'], diff:9, type:'reps', equip:'elevato', rep:[2,6], reg:'dragon_flag_negative',
      cues:['Corpo dritto che sale e scende dai fianchi','Solo le scapole a terra'], errori:['Rompere la linea del corpo'], desc:'Sollevamento e discesa del corpo teso perno sulle scapole: uno dei re degli addominali.' },

    /* ------------------------------------------------------------------ SKILL */
    { id:'wall_walk', name:'Wall walk (camminata al muro)', cat:'skill', muscles:['Spalle','Core'], diff:5, type:'reps', equip:'muro', rep:[3,6], prog:'wall_handstand_hold',
      cues:['Piedi al muro, cammina con le mani verso il muro','Corpo teso'], errori:['Schiena inarcata'], desc:'Sali verso la verticale camminando su per il muro: confidenza e forza a testa in giù.' },
    { id:'wall_handstand_hold', name:'Verticale al muro (tenuta)', cat:'skill', muscles:['Spalle','Core','Polsi'], diff:6, type:'hold', equip:'muro', hold:[15,45], reg:'wall_walk', prog:'chest_wall_handstand',
      cues:['Petto o schiena al muro, corpo lungo','Spingi il pavimento lontano'], errori:['Inarcare la schiena','Guardare i piedi'], desc:'Tenuta in verticale con supporto del muro: base per la verticale libera.' },
    { id:'chest_wall_handstand', name:'Verticale petto al muro', cat:'skill', muscles:['Spalle','Core'], diff:7, type:'hold', equip:'muro', hold:[15,40], reg:'wall_handstand_hold', prog:'freestanding_handstand',
      cues:['Sali con il petto rivolto al muro','Corpo perfettamente in linea'], errori:['Banana (schiena inarcata)'], desc:'Verticale con la pancia al muro: insegna l\'allineamento corretto della verticale.' },
    { id:'freestanding_handstand', name:'Verticale libera', cat:'skill', muscles:['Spalle','Core','Equilibrio'], diff:9, type:'hold', equip:'none', hold:[5,20], reg:'chest_wall_handstand',
      cues:['Dita che afferrano il suolo per bilanciare','Corpo lungo e attivo'], errori:['Cercare l\'equilibrio con la schiena'], desc:'La verticale in equilibrio senza supporto: controllo totale del corpo.' },
    { id:'planche_lean', name:'Planche lean', cat:'skill', muscles:['Spalle','Core','Polsi'], diff:5, type:'hold', equip:'none', hold:[15,30], prog:'frog_stand',
      cues:['In plank alto porta le spalle avanti oltre le mani','Scapole protratte'], errori:['Bacino che cede'], desc:'Inclinazione in avanti in appoggio: primo mattone della planche.' },
    { id:'frog_stand', name:'Frog stand (rana)', cat:'skill', muscles:['Spalle','Polsi','Core'], diff:5, type:'hold', equip:'none', hold:[15,40], reg:'planche_lean', prog:'tuck_planche',
      cues:['Ginocchia appoggiate sui gomiti','Sposta il peso avanti fino a staccare i piedi'], errori:['Guardare in basso'], desc:'Equilibrio sulle mani con le ginocchia sui gomiti: introduce il bilanciamento della planche.' },
    { id:'tuck_planche', name:'Planche raccolta (tuck)', cat:'skill', muscles:['Spalle','Core','Dorsali'], diff:7, type:'hold', equip:'none', hold:[8,20], reg:'frog_stand', prog:'adv_tuck_planche',
      cues:['Ginocchia raccolte, ma niente appoggio sui gomiti','Braccia tese, spalle protratte'], errori:['Gomiti piegati'], desc:'Planche con ginocchia raccolte e braccia tese: vera partenza della planche.' },
    { id:'adv_tuck_planche', name:'Planche tuck avanzata', cat:'skill', muscles:['Spalle','Core','Dorsali'], diff:8, type:'hold', equip:'none', hold:[6,15], reg:'tuck_planche', prog:'straddle_planche',
      cues:['Apri l\'angolo dell\'anca, schiena piatta','Bacino all\'altezza delle spalle'], errori:['Schiena arrotondata'], desc:'Tuck planche con schiena piatta e anche più aperte: aumenta la leva.' },
    { id:'straddle_planche', name:'Planche divaricata (straddle)', cat:'skill', muscles:['Spalle','Core','Dorsali'], diff:9, type:'hold', equip:'none', hold:[3,10], reg:'adv_tuck_planche', prog:'full_planche',
      cues:['Gambe tese e divaricate','Corpo parallelo al suolo'], errori:['Bacino alto'], desc:'Planche a gambe divaricate: leva quasi completa, altissima difficoltà.' },
    { id:'full_planche', name:'Planche completa', cat:'skill', muscles:['Spalle','Core','Dorsali'], diff:10, type:'hold', equip:'none', hold:[2,8], reg:'straddle_planche',
      cues:['Corpo teso e parallelo al suolo, gambe unite','Spinta enorme delle scapole'], errori:['Perdere l\'orizzontale'], desc:'Il corpo tenuto orizzontale sulle sole mani: una delle massime espressioni di forza.' },
    { id:'tuck_fl', name:'Front lever raccolto (tuck)', cat:'skill', muscles:['Dorsali','Core','Spalle'], diff:6, type:'hold', equip:'sbarra', hold:[10,25], prog:'adv_tuck_fl', floorAlt:'superman_hold',
      cues:['Appeso, porta le ginocchia al petto e la schiena orizzontale','Braccia tese, scapole depresse'], errori:['Spalle rilassate'], desc:'Front lever con ginocchia raccolte: base della leva frontale. Richiede la sbarra.' },
    { id:'adv_tuck_fl', name:'Front lever tuck avanzato', cat:'skill', muscles:['Dorsali','Core','Spalle'], diff:7, type:'hold', equip:'sbarra', hold:[8,18], reg:'tuck_fl', prog:'straddle_fl', floorAlt:'superman_hold',
      cues:['Apri le anche mantenendo la schiena orizzontale','Ginocchia lontane dal petto'], errori:['Bacino che scende'], desc:'Front lever tuck con anche più aperte: aumenta la leva. Richiede la sbarra.' },
    { id:'straddle_fl', name:'Front lever divaricato', cat:'skill', muscles:['Dorsali','Core','Spalle'], diff:9, type:'hold', equip:'sbarra', hold:[4,10], reg:'adv_tuck_fl', prog:'full_fl', floorAlt:'superman_hold',
      cues:['Gambe tese e divaricate, corpo orizzontale','Tira la barra verso i fianchi'], errori:['Anche basse'], desc:'Front lever a gambe divaricate: leva quasi completa. Richiede la sbarra.' },
    { id:'full_fl', name:'Front lever completo', cat:'skill', muscles:['Dorsali','Core','Spalle'], diff:10, type:'hold', equip:'sbarra', hold:[3,8], reg:'straddle_fl',
      cues:['Corpo dritto e orizzontale appeso alla barra','Massima tensione totale'], errori:['Rompere la linea del corpo'], desc:'Corpo teso orizzontale appeso alla sbarra: capolavoro di forza dei dorsali e del core.' },
    { id:'muscleup_transition', name:'Transizione muscle-up (negativa)', cat:'skill', muscles:['Dorsali','Tricipiti','Petto'], diff:8, type:'reps', equip:'sbarra', rep:[2,5], reg:'high_pullup', prog:'muscleup',
      cues:['Dall\'alto controlla lentamente la fase di transizione','Polsi che ruotano sopra la barra'], errori:['Cedere di colpo'], desc:'La fase di transizione del muscle-up allenata in negativa: sblocca il movimento completo.' },
    { id:'muscleup', name:'Muscle-up', cat:'skill', muscles:['Dorsali','Petto','Tricipiti','Core'], diff:9, type:'reps', equip:'sbarra', rep:[1,5], reg:'muscleup_transition',
      cues:['Tirata esplosiva, poi transizione sopra la barra','Corpo compatto, niente kip disordinato'], errori:['Slancio eccessivo delle gambe'], desc:'Dalla trazione fino a sopra la barra in un unico movimento: la skill dinamica più iconica.' },
    { id:'foot_lsit', name:'L-sit con appoggio piedi', cat:'skill', muscles:['Tricipiti','Addome','Spalle'], diff:4, type:'hold', equip:'elevato', hold:[15,30], prog:'tuck_lsit',
      cues:['Mani su due rialzi, piedi che sfiorano terra','Spingi le spalle in basso'], errori:['Spalle in su'], desc:'Sostegno a braccia tese su due rialzi con i piedi a terra: primo passo verso l\'L-sit.' },
  ];

  /* ------------------------------------------------------------- SKILL TREE ---
   * Percorsi guidati verso le skill iconiche. Ogni tappa punta a un esercizio
   * del database con un obiettivo (goal) di padronanza.
   */
  const SKILLS = [
    { id:'handstand', name:'Verticale (Handstand)', emoji:'🤸', color:'#22D3EE',
      desc:'Equilibrio e forza a testa in giù, dal muro alla verticale libera.',
      steps:[
        { ex:'scap_pushup', goal:'Controllo scapole' },
        { ex:'wall_walk', goal:'Salire al muro' },
        { ex:'wall_handstand_hold', goal:'45s al muro' },
        { ex:'chest_wall_handstand', goal:'30s petto al muro' },
        { ex:'freestanding_handstand', goal:'10s+ libera' },
      ] },
    { id:'planche', name:'Planche', emoji:'🦅', color:'#C6FF3D',
      desc:'La spinta orizzontale definitiva: dal lean alla planche completa.',
      steps:[
        { ex:'planche_lean', goal:'30s di lean' },
        { ex:'frog_stand', goal:'40s frog stand' },
        { ex:'tuck_planche', goal:'20s tuck' },
        { ex:'adv_tuck_planche', goal:'15s tuck avanzato' },
        { ex:'straddle_planche', goal:'Straddle planche' },
        { ex:'full_planche', goal:'Planche completa' },
      ] },
    { id:'front_lever', name:'Front Lever', emoji:'➖', color:'#A78BFA',
      desc:'Il corpo teso orizzontale alla sbarra: forza pura dei dorsali.',
      steps:[
        { ex:'tuck_fl', goal:'25s tuck' },
        { ex:'adv_tuck_fl', goal:'18s tuck avanzato' },
        { ex:'straddle_fl', goal:'10s straddle' },
        { ex:'full_fl', goal:'Front lever completo' },
      ] },
    { id:'muscle_up', name:'Muscle-up', emoji:'⚡', color:'#FB923C',
      desc:'Dalla trazione fino a sopra la barra: la skill dinamica per eccellenza.',
      steps:[
        { ex:'pullup', goal:'10 trazioni pulite' },
        { ex:'high_pullup', goal:'Petto alla barra' },
        { ex:'muscleup_transition', goal:'Transizione in negativa' },
        { ex:'muscleup', goal:'Primo muscle-up' },
      ] },
    { id:'l_sit', name:'L-sit', emoji:'📐', color:'#34D399',
      desc:'Sospensione a L: forza combinata di addome, spalle e tricipiti.',
      steps:[
        { ex:'foot_lsit', goal:'30s coi piedi a terra' },
        { ex:'tuck_lsit', goal:'25s tuck' },
        { ex:'lsit', goal:'L-sit 15s' },
      ] },
    { id:'pistol', name:'Pistol Squat', emoji:'🦵', color:'#F472B6',
      desc:'Accosciata completa su una gamba sola: forza, mobilità ed equilibrio.',
      steps:[
        { ex:'split_squat', goal:'15 per lato' },
        { ex:'bulgarian_split_squat', goal:'12 per lato' },
        { ex:'assisted_pistol', goal:'8 assistiti' },
        { ex:'box_pistol', goal:'6 su rialzo' },
        { ex:'pistol_squat', goal:'Pistol libero' },
      ] },
  ];

  /* ---------------------------------------------------------------- FASI ------
   * Le 5 fasi del percorso 0→100.
   */
  const PHASES = [
    { id:'fondamenta', name:'Fondamenta', from:1, to:15, color:'#34D399', emoji:'🌱',
      goal:'Costruire l\'abitudine e la tecnica di base: 10 piegamenti regolari, 20 squat, plank 45s.',
      focus:'Mobilità, schemi motori base, tenuta del core.' },
    { id:'costruzione', name:'Costruzione', from:16, to:40, color:'#22D3EE', emoji:'🔨',
      goal:'Forza full-body di base: 20 piegamenti, prime trazioni/negative, plank 60s, pike push-up.',
      focus:'Volume progressivo su spinta, trazione e gambe.' },
    { id:'forza', name:'Forza', from:41, to:65, color:'#C6FF3D', emoji:'🔥',
      goal:'Varianti più dure e split upper/lower: trazioni multiple, dip, hollow, pistol assistito.',
      focus:'Intensità e varianti a leva più difficile.' },
    { id:'avanzato', name:'Avanzato', from:66, to:85, color:'#FB923C', emoji:'💪',
      goal:'Unilaterali e pre-skill: archer, pistol, verticale al muro, L-sit, dragon flag.',
      focus:'Forza monopodalica/monobraccio e preparazione alle skill.' },
    { id:'elite', name:'Elite & Skill', from:86, to:100, color:'#F472B6', emoji:'🏆',
      goal:'Le grandi skill: planche, front lever, verticale libera, muscle-up.',
      focus:'Isometrie di forza avanzate e movimenti dinamici.' },
  ];

  // Indice per lookup rapido
  const BY_ID = {};
  E.forEach(function (ex) { BY_ID[ex.id] = ex; });

  CALI.exercises = E;
  CALI.exById = BY_ID;
  CALI.skills = SKILLS;
  CALI.phases = PHASES;
  CALI.catInfo = {
    warmup:   { label:'Riscaldamento', emoji:'🔥', color:'#FB923C' },
    mobility: { label:'Mobilità',      emoji:'🧘', color:'#A78BFA' },
    push:     { label:'Spinta',        emoji:'🙌', color:'#22D3EE' },
    pull:     { label:'Trazione',      emoji:'🧗', color:'#C6FF3D' },
    legs:     { label:'Gambe',         emoji:'🦵', color:'#F472B6' },
    core:     { label:'Core',          emoji:'🌀', color:'#34D399' },
    skill:    { label:'Skill',         emoji:'⭐', color:'#FBBF24' },
  };

})(window.CALI = window.CALI || {});
