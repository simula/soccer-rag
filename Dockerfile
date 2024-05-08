FROM python:3.11
RUN useradd -m -u 1000 user

WORKDIR /code

# RUN pip install soccernet
# RUN python -c "from SoccerNet.Downloader import SoccerNetDownloader; mySoccerNetDownloader = SoccerNetDownloader(LocalDirectory='data/dataset/SoccerNet'); mySoccerNetDownloader.downloadGames(files=['Labels-caption.json'], split=['train', 'valid', 'test']); mySoccerNetDownloader.downloadGames(files=['Labels-v2.json'], split=['train', 'valid', 'test'])"

COPY ./requirements.txt /code/requirements.txt


RUN pip install   -r /code/requirements.txt

COPY . .

# RUN python ./src/database.py


COPY ".env_demo" ".env"

RUN chmod -R 777 /code/

CMD ["chainlit", "run", "-h", "app.py", "--port", "7860"]
ENV INTERACTIVE_OPENAI_KEY=1