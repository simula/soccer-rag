from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, Float, Boolean, UniqueConstraint
from sqlalchemy.orm import declarative_base, sessionmaker
import pandas as pd
import os
import json

engine = create_engine('sqlite:///../../data/games.db', echo=False)
Base = declarative_base()


class Game(Base):
    __tablename__ = 'games'
    id = Column(Integer, primary_key=True)
    timestamp = Column(String)
    score = Column(String)
    goal_home = Column(Integer)
    goal_away = Column(Integer)
    round = Column(String)
    home_team_id = Column(Integer, ForeignKey('teams.id'))
    away_team_id = Column(Integer, ForeignKey('teams.id'))
    venue = Column(String)
    referee = Column(String)
    attendance = Column(String)
    date = Column(String)
    season = Column(String)
    league_id = Column(Integer, ForeignKey('leagues.id'))

class GameLineup(Base):
    __tablename__ = 'game_lineup'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    team_id = Column(Integer, ForeignKey('teams.id'))
    player_id = Column(Integer, ForeignKey('players.hash'))
    shirt_number = Column(String)
    position = Column(String)
    starting = Column(Boolean)
    captain = Column(Boolean)
    coach = Column(Boolean)
    tactics = Column(String)
    # Add a unique constraint on game_id and player_id
    __table_args__ = (UniqueConstraint('game_id', 'player_id', name='uc_game_id_player_id'),)


class Team(Base):
    __tablename__ = 'teams'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Player(Base):
    __tablename__ = 'players'
    hash = Column(String, primary_key=True)
    name = Column(String)
    country = Column(String)


class Caption(Base):
    __tablename__ = 'captions'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    game_time = Column(String)
    period = Column(Integer)
    label = Column(String)
    description = Column(Text)
    important = Column(Boolean)
    visibility = Column(Boolean)
    frame_stamp = Column(Integer)


class Commentary(Base):
    __tablename__ = 'commentary'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    period = Column(Integer)
    event_time_start = Column(Float)
    event_time_end = Column(Float)
    description = Column(Text)

class League(Base):
    __tablename__ = 'leagues'
    id = Column(Integer, primary_key=True)
    name = Column(String)

class Event(Base):
    __tablename__ = 'events'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    period = Column(Integer)
    # half = Column(Integer)
    game_time = Column(Integer)
    team_id = Column(Integer, ForeignKey('teams.id'))
    frame_stamp = Column(Integer)
    label = Column(String)
    visibility = Column(Boolean)

class Augmented_Team(Base):
    __tablename__ = 'augmented_teams'
    id = Column(Integer, primary_key=True)
    team_id = Column(Integer, ForeignKey('teams.id'))
    augmented_name = Column(String)

class Augmented_League(Base):
    __tablename__ = 'augmented_leagues'
    id = Column(Integer, primary_key=True)
    league_id = Column(Integer, ForeignKey('leagues.id'))
    augmented_name = Column(String)

class Player_Event_Label(Base):
    __tablename__ = 'player_event_labels'
    id = Column(Integer, primary_key=True)
    label = Column(String)

class Player_Event(Base):
    __tablename__ = 'player_events'
    id = Column(Integer, primary_key=True)
    game_id = Column(Integer, ForeignKey('games.id'))
    player_id = Column(Integer, ForeignKey('players.hash'))
    time = Column(String) # Time in minutes of the game
    type = Column(Integer, ForeignKey('player_event_labels.id'))
    linked_player = Column(Integer, ForeignKey('players.hash')) # If the event is linked to another player, for example a substitution







# Create Tables
Base.metadata.create_all(engine)

# Session setup
Session = sessionmaker(bind=engine)

def extract_time_from_player_event(time:str)->str:
    # Extract the time from the string
    time = time.split("'")[0] # Need to keep it str because of overtime eg. (45+2)
    return time

def get_or_create(session, model, **kwargs):
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance
    else:
        instance = model(**kwargs)
        session.add(instance)
        session.commit()
        return instance

def process_game_data(data,data2, league, season):
    session = Session()
    # Caption = d and v2 = d2
    home_team = data["gameHomeTeam"]
    away_team = data["gameAwayTeam"]
    score = data["score"]
    home_score = score[0]
    away_score = score[-1]
    round_ = data["round"]
    venue = data["venue"][0]
    referee = data.get("referee_found", None)
    referee = referee[0] if referee else data.get("referee", None)
    date = data["gameDate"]
    timestamp = data["timestamp"]
    attendance = data.get("attendance", [])
    attendance = attendance[0] if attendance else None

    home_team = get_or_create(session, Team, name=home_team)
    away_team = get_or_create(session, Team, name=away_team)
    # Check if the game already exists
    game = session.query(Game).filter_by(timestamp=timestamp, home_team_id=home_team.id).first()
    # Check if league exists
    league = get_or_create(session, League, name=league)
    if not game:
        game = Game(timestamp=timestamp, score=score, goal_home=home_score, goal_away=away_score, round=round_, home_team_id=home_team.id, away_team_id=away_team.id,
                    venue=venue, date=date, attendance=attendance, season=season, league_id=league.id, referee=referee)
        session.add(game)
        session.commit()

    teams = ["home", "away"]
    # Lets add lineup data
    for team in teams:
        if team == "home":
            team_id = home_team.id
        else:
            team_id = away_team.id
        team_lineup = data["lineup"][team]
        tactic = team_lineup["tactic"]

        for player_data in team_lineup["players"]:
            player_hash = player_data["hash"]
            name = player_data["long_name"]
            if " " not in name: # Since some players are missing their first name, do this to help with the search
                name = "NULL " + name
            number = player_data["shirt_number"]
            captain = player_data["captain"] == "(C)"
            starting = player_data["starting"]
            country = player_data["country"]
            position = player_data["lineup"]
            facts = player_data.get("facts", None) # Facts might be empty





            player = get_or_create(session, Player, hash=player_hash, name=name, country=country)
            game_lineup = GameLineup(game_id=game.id, team_id=team_id, player_id=player.hash,
                                     shirt_number=number, position=position, starting=starting, captain=captain, coach=False, tactics=tactic)
            if facts:
                for fact in facts:
                    type = fact["type"]
                    time = extract_time_from_player_event(fact["time"])
                    event = get_or_create(session, Player_Event_Label, id=int(type))
                    linked_player = fact.get("linked_player_hash", None)

                    player_event = Player_Event(game_id=game.id, player_id=player.hash, time=time, type=event.id, linked_player=linked_player)
                    session.add(player_event)
            session.add(game_lineup)

        # Get the coach
        coach = team_lineup["coach"][0]
        coach_hash = coach["hash"]
        coach_name = coach["long_name"]
        if " " not in coach_name:  # Since some players are missing their first name, do this to help with the search
            name = "NULL " + coach_name
        coach_country = coach["country"]
        coach_player = get_or_create(session, Player, hash=coach_hash, name=coach_name, country=coach_country)
        game_lineup = GameLineup(game_id=game.id, team_id=team_id, player_id=coach_player.hash,
                                 shirt_number=None, position=None, starting=None, captain=False, coach=True, tactics=tactic)
        session.add(game_lineup)

        # Commit all changes at once
        session.commit()

    # Start parsing the events
    events = data["annotations"]
    for event in events:
        period, time = convert_to_seconds(event["gameTime"])
        label = event["label"]
        # Renaming labels
        if label == "soccer-ball":
            label = "goal"
        elif label == "y-card":
            label = "yellow card"
        elif label == "r-card":
            label = "red card"
        
        description = event["description"]
        important = event["important"] == "true"
        visible = event["visibility"]
        # Convert to boolean
        # True if shown, False if not
        visible = visible == "shown"
        position = int(event["position"])

        event = Caption(game_id=game.id, game_time=time, period=period, label=label, description=description,
                        important=important, visibility=visible, frame_stamp=position)
        session.add(event)
    session.commit()

    return game.id, home_team.id, away_team.id

def process_player_data(data):
    pass

def process_ASR_data(data, game_id, period):
    session = Session()
    seg = data["segments"]
    commentary_events = []  # Store the events in a list

    for k, v in seg.items():
        start = float(v[0])
        end = float(v[1])
        desc = v[2]
        event = Commentary(game_id=game_id, period=period, event_time_start=start, event_time_end=end, description=desc)
        commentary_events.append(event)

    # Bulk save objects
    session.bulk_save_objects(commentary_events)
    session.commit()
    session.close()

def convert_to_seconds(time_str):
    # Split the string into its components
    period, time = time_str.split(" - ")
    minutes, seconds = time.split(":")

    # Convert the components to integers
    period = int(period)
    minutes = int(minutes)
    seconds = int(seconds)
    # Calculate the time in seconds

    total_seconds = (minutes * 60) + seconds
    return period, total_seconds


def parse_labels_v2(data, session, home_team_id, away_team_id, game_id):
    annotations_data = data["annotations"]
    no_team = get_or_create(session, Team, name="not applicable")

    for annotation in annotations_data:
        period, game_time = convert_to_seconds(annotation["gameTime"])

        # Determine which team the annotation belongs to
        if annotation["team"] == "home":
            team_id = home_team_id
        elif annotation["team"] == "away":
            team_id = away_team_id
        else:
            team_id = no_team.id

        position = annotation.get("position", None)  # Assuming position can be null
        visibility = annotation["visibility"] == "visible"
        # Convert to boolean
        # True if visible, False if not
        visibility = visibility == "visible"
        label = annotation["label"]

        # Create and add the Annotations instance
        annotation_entry = Event(
            game_id=game_id,
            period=period,  # periode
            game_time=game_time,  # Already in seconds
            frame_stamp=position,  # Make sure this is an integer or None
            team_id=team_id,  # Integer ID of the team
            visibility=visibility, # Boolean
            label=label # String with information
        )
        session.add(annotation_entry)

    session.commit()





def process_json_files(directory):
    session = Session()
    fill_player_events(session)
    for root, dirs, files in os.walk(directory):
        print(root)
        labels_file = None
        asr_files = []
        path_parts = root.split("\\")
        if len(path_parts) > 2:
            league = path_parts[-3].split("/")[-1]
            season = path_parts[-2]
        # Need the labels-v2 first as it contains the game ID
        for file in files:
            if 'Labels-caption.json' in file:
                labels_file = file
            elif file.endswith('.json'):
                asr_files.append(file)

        if labels_file:
            with open(os.path.join(root, labels_file), 'r') as f:
                lb_cap = json.load(f)
            with open(os.path.join(root, "Labels-v2.json"), 'r') as f:
                lb_v2 = json.load(f)
            game_id, home_team_id, away_team_id = process_game_data(lb_cap,lb_v2, league, season)

        for file in asr_files:
            with open(os.path.join(root, file), 'r') as f:
                asr = json.load(f)

            # Determine the type of file and process accordingly
            if 'Labels-v2' in file:
                parse_labels_v2(asr, session, home_team_id, away_team_id, game_id)

            elif '1_half-ASR' in file:
                period = 1
                # Parse and commit the data
                process_ASR_data(data=asr, game_id = game_id, period=period)

            elif '2_half-ASR' in file:
                period = 2
                # Parse and commit the data
                process_ASR_data(data=asr, game_id = game_id, period=period)


    session.commit()
    session.close()

def fill_player_events(session):

    fact_id2label = {
        "1": "Yellow card",
        # Example: "time": "71' Ivanovic B. (Unsportsmanlike conduct)", "description": "Yellow Card"
        "2": "Red card",  # Example: "time": "70' Matic N. (Unsportsmanlike conduct)", "description": "Red Card"
        "3": "Goal",  # Example: "time": "14' Ivanovic B. (Hazard E.)", "description": "Goal"
        "4": "NA",
        "5": "NA 2",
        "6": "Substitution home",  # Example: "time": "72'", "description": "Ramires"
        "7": "Substitution away",  # Example: "time": "86'", "description": "Filipe Luis"
        "8": "Assistance"  # Example: "time": "14' Ivanovic B. (Hazard E.)", "description": "Assistance"
    }
    for key, value in fact_id2label.items():
        label = get_or_create(session, Player_Event_Label, label=value)
    session.commit()



def fill_Augmented_Team(file_path):

    df = pd.read_csv(file_path)
    # the df should have two columns, team_name and augmented_name

    session = Session()
    teams = session.query(Team).all()
    # For each row, find the team_id and add the augmented name
    for index, row in df.iterrows():
        team_name = row["name"]
        augmented_name = row["augmented_name"]
        # Strip leading and trailing whitespace
        augmented_name = augmented_name.strip()
        team = session.query(Team).filter_by(name=team_name).first()
        if team:
            augmented_team = get_or_create(session, Augmented_Team, team_id=team.id, augmented_name=augmented_name)
    session.commit()
    session.close()

def fill_Augmented_League(file_path):
    # Read the csv file
    df = pd.read_csv(file_path)
    # the df should have two columns, team_name and augmented_name

    session = Session()
    leagues = session.query(League).all()
    # For each row, find the team_id and add the augmented name
    for index, row in df.iterrows():
        league_name = row["name"]
        augmented_name = row["augmented_name"]
        # Strip leading and trailing whitespace
        augmented_name = augmented_name.strip()
        league = session.query(League).filter_by(name=league_name).first()
        if league:
            augmented_league = get_or_create(session, Augmented_League, league_id=league.id, augmented_name=augmented_name)
    session.commit()
    session.close()

if __name__ == "__main__":
    # Example directory path
    process_json_files('../data/Dataset/SoccerNet/')
    fill_Augmented_Team('../data/dataset/augmented_teams.csv')
    fill_Augmented_League('../data/dataset/augmented_leagues.csv')
# Rename the event/annotation table to something more descriptive. Events are fucking everything else over

