from flask import Flask, request, jsonify, g
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
import os

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
    """docstring for Product."""
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
    titile = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    max_time = db.Column(db.Integer, nullable=True)

@app.route('/api/users', methods = ['POST'])
def new_user():
    name = request.json.get('name')
    email = request.json.get('email')
    password = request.json.get('password')
    is_teacher = request.json.get('is_teacher')
    if email is None or password is None:
        abort(400) # missing arguments
    if User.query.filter_by(email = email).first() is not None:
        abort(400) # existing user
    user = User(name = name, email = email, is_teacher = is_teacher)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({ 'email': user.email, "status" : "success" })

@auth.verify_password
def verify_password(email, password):
    user = User.query.filter_by(email = email).first()
    if not user or not user.verify_password(password):
        return False
    g.user = user
    return True

@app.route('/api/dashboard/')
@auth.login_required
def get_dashboard():
    # tests = Test.query.all();
    # results = auth.results
    # if auth.is_teacher:

    return jsonify({ 'status':"success" })



# class UserSchema(ma.Schema):
#     class Meta:
#         fields = ('id', 'name', 'email', 'password')
#
# #Init Schema
# user_schema = UserSchema()
# users_schema =  UserSchema(many=True)


#Run server
if __name__ == '__main__':
    app.run(debug=True)
