# Flappy Bird Reglerteorilabb

Detta program är ett Flappy Bird-spel för undervisning i ET050G - Reglerteknik vid Mittuniversitetet, utvecklat av Roger Olsson tillsammans med OpenAI GPT-5.4. 

Du kan spela själv i manuellt läge eller låta en regulator (autopilot) styra fågeln i automatiskt läge. Oavsett vilket läge du väljer används samma fågelmodell, samma gravitation, samma rör och samma poängräkning, så att du rättvist kan jämföra reglulatorimplementationer.

## Syfte

Appen är till för att du som student ska kunna:
- jämföra manuell styrning med automatisk reglering
- se hur val av regulatorparametrar påverkar spelet
- observera hur en och samma process kan styras på olika sätt

Fågeln är processen. En flaxning är insignal. Regulatorn försöker hålla fågeln på rätt höjd för att passera genom rören.

## Spellägen

### Manuellt spel
Du styr fågeln själv med tangentbordet.

### Automatiskt spel
Du väljer regulator, ställer in parametrar och startar sedan rundan. Regulatorn spelar då spelet åt dig.

## Poäng och topplista

- Poäng är antal passerade rörpar innan kollision.
- Manuella resultat sparas separat från automatiska resultat.
- För automatiska resultat sparas regulatorns parametrar tillsammans med resultatet.

## Kontroller

### Gemensamt
- `M`: byt till manuellt läge
- `A`: byt till automatiskt läge
- `R`: återställ rundan och återgå till Redo
- `Esc`: återställ rundan och återgå till Redo

### Vid numerisk inmatning
- `0-9`, `-`, `.`: skriv in ett numeriskt värde
- `Backsteg`: radera senaste tecknet
- `Enter`: bekräfta värdet
- `Esc`: avbryt redigeringen

### Manuellt spel
- `Blanksteg`: starta rundan och få fågeln att flaxa
- `Tab`: välj hastighetsökning
- `Enter`: skriv in ett exakt värde för hastighetsökningen

### Automatiskt spel
- `1/2/3`: välj regulatorfamilj
- `Tab`: välj parameter
- `Enter`: skriv in ett exakt numeriskt värde för vald parameter
- `Blanksteg`: starta rundan med aktuell regulator

## Sa anvander du appen

### Om du vill spela själv
1. Starta appen.
2. Tryck `M` för manuellt läge om det inte redan är valt.
3. Tryck `Blanksteg` för att starta.
4. Fortsätt trycka `Blanksteg` för att styra fågeln genom rören.

### Om du vill prova automatisk styrning
1. Tryck `A` för automatiskt läge.
2. Välj regulator med `1`, `2` eller `3`.
3. Välj parameter med `Tab`.
4. Tryck `Enter` för att skriva in ett exakt värde.
5. Tryck `Blanksteg` för att starta rundan.
6. Jämför resultatet med topplistan.

## Installation

```bash
python -m pip install -r requirements.txt
python FlappyBirdLight.py
```

## Repostruktur

- `FlappyBirdLight.py`: startpunkt som startar appen.
- `flappy_control/core.py`: fysikmodell, pipes, kollisionslogik och poangrakning.
- `flappy_control/controllers.py`: pa-av-, PID- och overforingsfunktionsregulatorer.
- `flappy_control/ui.py`: PyGame-granssnitt, inmatning, visning och topplistor.
- `flappy_control/analytics.py`: analys- och modelleringsfunktioner for vidareutveckling och laborationer.
- `tests/`: automatiserade regressionstester for simulering, regulatorer, analys och UI-tillstand.
- `flappy-bird-assets/`: spelresurser samt tillhorande dokumentation och licensinformation for assets.
- `DEVELOPER.md`: utvecklarorienterad guide for underhall och vidareutveckling.
- `SDP.md`: overgripande produkt- och utvecklingsplan.
- `CHANGELOG.md`: historik over andringar i projektet.

## For utveckling och verifiering

Om du arbetar i repot och vill verifiera andringar finns automatiserade tester:

```bash
python -m unittest discover -s tests -v
```

## Lokala filer

- `high_scores.json` skapas lokalt nar appen kor och innehaller topplistor for manuellt och automatiskt spel.
- `__pycache__/` och `*.pyc` ar cachefiler fran Python-korning och hor inte till den dokumenterade programlogiken.

## Dokumentation i repot

- `README.md` riktar sig till studenter och beskriver hur appen anvands.
- `SDP.md` beskriver ett bredare projekt- och produktperspektiv kring arbetet.

## Licens

- Kallkoden i repot omfattas av `LICENSE`.
- Assets i `flappy-bird-assets/` har egen dokumentation och licensinformation i den katalogen.

