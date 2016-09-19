from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database_setup import Animal, Base, Breed, User

engine = create_engine('sqlite:///animalappwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create dummy user
User1 = User(name="Robo Barista", email="tinnyTim@udacity.com",
             picture='https://pbs.twimg.com/profile_images/2671170543/18debd694829ed78203a5a36dd364160_400x400.png')
session.add(User1)
session.commit()

#Create a lot of animals
animal1 = Animal(user_id=1, name="Snake")

session.add(animal1)
session.commit()

breed1 = Breed(user_id=1, name="Python", description="Most members of this family are ambush predators.",
                animal = animal1)
session.add(breed1)
session.commit()

breed2 = Breed(user_id=1, name="Naja", description="A genus of venomous elapid snakes known as cobras.",
                animal = animal1)
session.add(breed2)
session.commit()

print "added some animals!"