from flask import Flask, request, jsonify, g, abort
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
import json
import os
import random
import string
import base64

#Init app
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
auth = HTTPBasicAuth()
#Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'test.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#Init db
db = SQLAlchemy(app)
#Init ma
ma = Marshmallow(app)


#Product
results = db.Table('results',
        db.Column('user_id', db.Integer, db.ForeignKey('user.id')),
        db.Column('test_id', db.Integer, db.ForeignKey('test.id')),
        db.Column('score', db.Integer, nullable=False)
    )

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255))
    is_teacher = db.Column(db.Integer, nullable=False)
    tests = db.relationship('Test', backref=db.backref('author', lazy=True), lazy='dynamic')
    resutls = db.relationship('Test', secondary=results, backref=db.backref('students', lazy='dynamic'))

    def hash_password(self, password):
        self.password = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    max_time = db.Column(db.Integer, nullable=True)

class TestSchema(ma.ModelSchema):
    class Meta:
        fields = ("id", "title", "created_by", "max_score", "max_time")

test_schema = TestSchema()
tests_scema = TestSchema(many=True)

@app.route('/api/users', methods = ['POST'])
def new_user():
    name = request.json.get('name')
    email = request.json.get('email')
    password = request.json.get('password')
    is_teacher = request.json.get('isTeacher')
    if email is None or password is None:
        abort(400) # missing arguments
    if User.query.filter_by(email = email).first() is not None:
        abort(400) # existing user
    user = User(name = name, email = email, is_teacher = is_teacher)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, 'email': user.email, "status" : "success" })

@auth.verify_password
def verify_password(email, password):
    user = User.query.filter_by(email = email).first()
    if not user or not user.verify_password(password):
        return False
    g.user = user
    return True

@app.route('/api/tests')
@auth.login_required
def get_dashboard():
    user = User.query.filter_by(email = auth.username()).first()
    all_tests = [test_schema.dump(test) for test in Test.query.all()]
    teacher_tests = [test_schema.dump(test) for test in user.tests.all()]
    if user.is_teacher:
        response = {
            "email": user.email,
            "tests": teacher_tests,
            "isTeacher": 1
        } 
    else:
        response = {
            "email": user.email,
            "tests": all_tests,
            "isTeacher": 0
        }
    return jsonify(response)


@app.route('/api/tests/create', methods=["POST"])
@auth.login_required
def add_test():
    title = request.json.get("title")
    test_file = base64.b64decode(request.json.get("file"))
    path = put_test_file(test_file)
    max_score = get_max_score(path)
    max_time  = request.json.get("maxTime") if request.json.get("maxTime") else None
    user = User.query.filter_by(email = auth.username()).first()

    test = Test(title=title, path=path, max_score=max_score, max_time=max_time, created_by=user.id)
    db.session.add(test)
    db.session.commit()
    return jsonify({"title": title, "created_by": user.id, "path": test.path})

def get_max_score(path):
    f = open(path, 'r')
    num_lines = sum(1 for line in open(path))
    return num_lines

def put_test_file(bin):
    s = string.ascii_lowercase+string.digits
    name = ''.join(random.sample(s,10))
    name+='.csv'
    path = os.path.dirname(os.path.abspath(__file__))
    new_file_path = os.path.join(path, name)
    f = open(new_file_path, 'wb')
    f.write(bin)
    f.close()
    return new_file_path

def create_json(path):
    f = open(path, 'r')
    questions = []
    for line in f.readlines():
        line = line.replace("\n", "")
        print(line)
        arr = line.split(';')
        print(arr)
        quest = arr[0]
        answers = []
        for i in range(1, 5):
            is_right = True if int(arr[5]) == i else False
            answers.append({
                "answer" : arr[i],
                "isRight": is_right
            })
        img = arr[6]
        questions.append({
            "question" : quest,
            "answers": answers,
            "img": img
        })
    f.close()
    return questions


@app.route('/api/tests/<int:test_id>')
@auth.login_required
def get_test(test_id):
    test = Test.query.filter_by(id=test_id).first()
    return jsonify(create_json(test.path))
    

#Run server
if __name__ == '__main__':
    app.run(debug=True)
