from flask import Flask, render_template, request, redirect, jsonify, url_for, flash
from sqlalchemy import create_engine, asc
from sqlalchemy.orm import sessionmaker
from database_setup import Base, Animal, Breed, User
from flask import session as login_session
import random
import string
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
from flask import make_response
import requests

app = Flask(__name__)

CLIENT_ID = json.loads(
    open('client_secrets.json', 'r').read())['web']['client_id']
APPLICATION_NAME = "Zootopia"

# Connect to Database and create database session
engine = create_engine('sqlite:///animalappwithusers.db')
Base.metadata.bind = engine

DBSession = sessionmaker(bind=engine)
session = DBSession()

# Create anti-forgery state token
@app.route('/login')
def showLogin():
    state = ''.join(
        random.choice(string.ascii_uppercase + string.digits) for x in range(32))
    login_session['state'] = state
    return render_template('login.html', STATE=state)

#Create a function to login with google plus account
@app.route('/gconnect', methods=['POST'])
def gconnect():

    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    request.get_data()
    code = request.data.decode('utf-8')

    try:
        oauth_flow = flow_from_clientsecrets('client_secrets.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    access_token = credentials.access_token
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    response = h.request(url, 'GET')[1]
    str_response = response.decode('utf-8')
    result = json.loads(str_response)

    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'

    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    login_session['access_token'] = access_token
    login_session['gplus_id'] = gplus_id

    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']
    login_session['picture'] = data['picture']
    login_session['email'] = data['email']

    user_id = getUserID(login_session['email'])
    if not user_id:
        user_id = createUser(login_session)
    login_session['user_id'] = user_id

    output = ''
    output += '<h1>Welcome, '
    output += login_session['username']
    output += '!</h1>'
    output += '<img src="'
    output += login_session['picture']
    output += ' " style = "width: 300px; height: 300px;border-radius: 150px;-webkit-border-radius: \
    150px;-moz-border-radius: 150px;"> '
    flash("you are now logged in as %s" % login_session['username'])
    return output

# Create some helper functions
def createUser(login_session):
    """Create a user using the information stored in login_session

    Args: 
        login_session: userinfo stored in it
    Returns:
        user.id
    """
    newUser = User(name=login_session['username'], email=login_session[
                   'email'], picture=login_session['picture'])
    session.add(newUser)
    session.commit()
    user = session.query(User).filter_by(email=login_session['email']).one()
    return user.id


def getUserInfo(user_id):
    """Get a user's information by using its user_id

    Args:
        user_id: the id of a user
    Returns:
        user
    """
    user = session.query(User).filter_by(id=user_id).one()
    return user


def getUserID(email):
    """Get a user's id by using its email

    Args:
        email
    Returns:
        user.id
    """
    try:
        user = session.query(User).filter_by(email=email).one()
        return user.id
    except:
        return None

# Create a function to disconnect a connected user
@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is None:
        response = make_response(
            json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % access_token
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        del login_session['email']
        del login_session['picture']

        response = make_response(json.dumps('Successfully disconnected.'), 200)
        response.headers['Content-Type'] = 'application/json'
        return redirect(url_for('showAnimals'))
    else:
        response = make_response(
            json.dumps('Failed to revoke token for given user.', 400))
        response.headers['Content-Type'] = 'application/json'
        return response

# Create some JSON APIs 
@app.route('/animal/<int:animal_id>/breed/JSON')
def animalBreedJSON(animal_id):
    animal = session.query(Animal).filter_by(id=animal_id).one()
    breeds = session.query(Breed).filter_by(
        animal_id=animal_id).all()
    return jsonify(Breeds=[i.serialize for i in breeds])


@app.route('/animal/<int:animal_id>/breed/<int:breed_id>/JSON')
def breedJSON(animal_id, breed_id):
    Breed_One = session.query(Breed).filter_by(id=breed_id).one()
    return jsonify(Breed_One=Breed_One.serialize)


@app.route('/animal/JSON')
def animalsJSON():
    animals = session.query(Animal).all()
    return jsonify(animals=[r.serialize for r in animals])

# Show all animals
@app.route('/')
@app.route('/animal/')
def showAnimals():
    animals = session.query(Animal).order_by(asc(Animal.name))
    if 'username' not in login_session:
        return render_template('publicanimals.html', animals=animals)
    else:
        return render_template('animals.html', animals=animals)

# Create a new animal
@app.route('/animal/new/', methods=['GET', 'POST'])
def newAnimal():
    if 'username' not in login_session:
        return redirect('/login')
    if request.method == 'POST':
        newAnimal = Animal(
            name=request.form['name'], user_id=login_session['user_id'])
        session.add(newAnimal)
        flash('New Animal %s Successfully Created' % newAnimal.name)
        session.commit()
        return redirect(url_for('showAnimals'))
    else:
        return render_template('newAnimal.html')

# Edit an animal
@app.route('/animal/<int:animal_id>/edit/', methods=['GET', 'POST'])
def editAnimal(animal_id):
    editedAnimal = session.query(
        Animal).filter_by(id=animal_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if editedAnimal.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert\
        ('You are not authorized to edit this animal.');}\
        </script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedAnimal.name = request.form['name']
            flash('Animal Successfully Edited %s' % editedAnimal.name)
            return redirect(url_for('showAnimals'))
    else:
        return render_template('editAnimal.html', animal=editedAnimal)

# Delete an animal
@app.route('/animal/<int:animal_id>/delete/', methods=['GET', 'POST'])
def deleteAnimal(animal_id):
    animalToDelete = session.query(
        Animal).filter_by(id=animal_id).one()
    if 'username' not in login_session:
        return redirect('/login')
    if animalToDelete.user_id != login_session['user_id']:
        return "<script>function myFunction() {alert\
        ('You are not authorized to delete this animal.');}\
        </script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(animalToDelete)
        flash('%s Successfully Deleted' % animalToDelete.name)
        session.commit()
        return redirect(url_for('showAnimals', animal_id=animal_id))
    else:
        return render_template('deleteAnimal.html', animal=animalToDelete)

# Show an animal breed
@app.route('/animal/<int:animal_id>/')
@app.route('/animal/<int:animal_id>/breed/')
def showBreed(animal_id):
    animal = session.query(Animal).filter_by(id=animal_id).one()
    creator = getUserInfo(animal.user_id)
    breeds = session.query(Breed).filter_by(
        animal_id=animal_id).all()
    if 'username' not in login_session or creator.id != login_session['user_id']:
        return render_template('publicbreed.html', breeds=breeds, animal=animal, creator=creator)
    else:
        return render_template('breed.html', breeds=breeds, animal=animal, creator=creator)

# Create a new breed
@app.route('/animal/<int:animal_id>/breed/new/', methods=['GET', 'POST'])
def newBreed(animal_id):
    if 'username' not in login_session:
        return redirect('/login')
    animal = session.query(Animal).filter_by(id=animal_id).one()
    if login_session['user_id'] != animal.user_id:
        return "<script>function myFunction() {alert\
        ('You are not authorized to add breeds to this animal.');}\
        </script><body onload='myFunction()''>"
    if request.method == 'POST':
        newBreed = Breed(name=request.form['name'], description=request.form['description'], 
        				animal_id=animal_id, user_id=animal.user_id)
        session.add(newBreed)
        session.commit()
        flash('New Breed %s Successfully Created' % (newBreed.name))
        return redirect(url_for('showBreed', animal_id=animal_id))
    else:
        return render_template('newbreed.html', animal_id=animal_id)

# Edit a breed
@app.route('/animal/<int:animal_id>/breed/<int:breed_id>/edit', methods=['GET', 'POST'])
def editBreed(animal_id, breed_id):
    if 'username' not in login_session:
        return redirect('/login')
    editedBreed = session.query(Breed).filter_by(id=breed_id).one()
    animal = session.query(Animal).filter_by(id=animal_id).one()
    if login_session['user_id'] != animal.user_id:
        return "<script>function myFunction() {alert\
        ('You are not authorized to edit breeds to this animal.');}\
        </script><body onload='myFunction()''>"
    if request.method == 'POST':
        if request.form['name']:
            editedBreed.name = request.form['name']
        if request.form['description']:
            editedBreed.description = request.form['description']
        session.add(editedBreed)
        session.commit()
        flash('Breed Successfully Edited')
        return redirect(url_for('showBreed', animal_id=animal_id))
    else:
        return render_template('editbreed.html', animal_id=animal_id, breed_id=breed_id, breed=editedBreed)

# Delete a breed
@app.route('/animal/<int:animal_id>/breed/<int:breed_id>/delete', methods=['GET', 'POST'])
def deleteBreed(animal_id, breed_id):
    if 'username' not in login_session:
        return redirect('/login')
    animal = session.query(Animal).filter_by(id=animal_id).one()
    breedToDelete = session.query(Breed).filter_by(id=breed_id).one()
    if login_session['user_id'] != animal.user_id:
        return "<script>function myFunction() {alert\
        ('You are not authorized to delete breeds to this animal.');}\
        </script><body onload='myFunction()''>"
    if request.method == 'POST':
        session.delete(breedToDelete)
        session.commit()
        flash('Breed Successfully Deleted')
        return redirect(url_for('showBreed', animal_id=animal_id))
    else:
        return render_template('deletebreed.html', breed=breedToDelete)

if __name__ == '__main__':
    app.secret_key = 'super_secret_key'
    app.debug = True
    app.run(host='0.0.0.0', port=8000)

