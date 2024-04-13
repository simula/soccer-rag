# SoccerRAG: Multimodal Soccer Information Retrieval via Natural Queries

## Setup
````bash
pip install -r requirements.txt
````
Rename .env_demo to .env and fill in the required fields.

## Setting up the database

### Required data
The data required to run the code is not included in this repository. 
The data can be downloaded from the [Soccernet](https://www.soccer-net.org/data).
Files needed are:
* Labels-v2.json [link](https://www.soccer-net.org/data#h.5klq86rmgt96)
* Labels-captions.json

The data should be placed in the ./data/Dataset/SoccerNet/ directory
For each league, create a new folder with the name of the leauge
For each season create a new folder with the name of the season (YYYY-YYYY)
For each game create a new folder with the name of the game (YYYY-MM-DD - HomeTeam Score - Score AwayTeam)
In each game folder, place the Labels-v2.json and Labels-captions.json files

### Setting up and populating the database
To set up the database, execute the following command:
````bash
python src/database.py
````
Adjust the path to the data in the database.py file as needed.

## Running the code
To run the code, execute the following command:
````bash
python main.py
````
The code will prompt you to enter a natural language query.

````angular2html
Enter a query: How many goals has Messi scored each season?
Lionel Messi has scored the following number of goals each season:
- 2014-2015: 13 goals
- 2015-2016: 3 goals
- 2016-2017: 31 goals
````

## Results
..

## Acknowledgements
..

## Citation
..

