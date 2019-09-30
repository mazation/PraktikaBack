from flask import Flask, request, jsonify, g, abort # Импортируем библиотеки для работы Flask
from flask_sqlalchemy import SQLAlchemy # Импортируем библиотеку для создания ORM
from flask_marshmallow import Marshmallow # Импортируем библиотеку для сериализации моделей
from flask_httpauth import HTTPBasicAuth # Импортируем библиотеку для автоматизации авторизации пользователя
from passlib.apps import custom_app_context as pwd_context # Импортируем библиотеку для шифрования пароля
import json # Модуль для создания json
import os # Модуль для взаимодействия с ОС
import random # Модуль для генерации случайных симоволов
import string # Модуль для операций со строками
import base64 # Модуль для шифрования/дешифрования в base64

#Объявляем переменную app, через которую получаем доступ к функциям Flask
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
auth = HTTPBasicAuth()
#Подключаем БД
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'test.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

#Объявляем переменную db, через которую получаем доступ к функциям SQLAlchemy
db = SQLAlchemy(app)
#Объявляем переменную ma, через которую получаем доступ к функциям Marshmallow
ma = Marshmallow(app)

#Создаем модель пользователя
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255))
    is_teacher = db.Column(db.Integer, nullable=False)
    tests = db.relationship('Test', backref=db.backref('author', lazy=True), lazy='dynamic') #Связь с моделью тест
    finished_tests = db.relationship('Result', back_populates="user") #Связь с моделью тест через ассоциацию результат
    #Добавляем метод для шифрования пароля
    def hash_password(self, password):
        self.password = pwd_context.encrypt(password)
    #Добавляем метод для верификации пароля
    def verify_password(self, password):
        return pwd_context.verify(password, self.password)

#Создаем модель теста
class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    path = db.Column(db.String(1000), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    max_score = db.Column(db.Integer, nullable=False)
    max_time = db.Column(db.Integer, nullable=True)
    students = db.relationship('Result', back_populates="finished_test")

#Создаем модель результата, которая является ассоциацией между моделями пользователь и тест
class Result(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'))
    score = db.Column(db.Integer, nullable=False)

    user = db.relationship('User', back_populates="finished_tests")#Связь модели пользователь с моделью тест
    finished_test = db.relationship('Test', back_populates="students")#Связь модели тест с моделью пользователь

#Объявляем схему сериализации для теста с полями для отправки на фронтенд
class TestSchema(ma.ModelSchema):
    class Meta:
        fields = ("id", "title", "created_by", "max_score", "max_time")

test_schema = TestSchema()
tests_scema = TestSchema(many=True)


#Объявляем схему сериализации для пользователя с полями для отправки на фронтенд
class UserSchema(ma.ModelSchema):
    results = ma.Nested(ResultSchema, many=True)
    class Meta:
        model = User

user_schema = UserSchema()
users_schema = UserSchema(many=True)

#Объявляем схему сериализации для результата с полями для отправки на фронтенд
class ResultSchema(ma.ModelSchema):
    class Meta:
        model = Result
        fields = ('id', 'finished_test.title', 'score', 'user.name')

result_schema = ResultSchema()
results_schema = ResultSchema(many=True)


#Создаем АПИ рут для запросов на создание пользователей
@app.route('/api/users', methods = ['POST'])
def new_user():
    name = request.json.get('name')
    email = request.json.get('email')
    password = request.json.get('password')
    is_teacher = request.json.get('isTeacher')
    #Если не указан эмейл или пароль, возвращается ошибка
    if email is None or password is None:
        abort(400) 
    #Если пользователь уже существует, то возвращается ошибка
    if User.query.filter_by(email = email).first() is not None:
        abort(400) 
    user = User(name = name, email = email, is_teacher = is_teacher)
    user.hash_password(password) #хешируем пароль
    db.session.add(user) #добвляем запись о пользователе в таблицу
    db.session.commit() #сохраняем запись о пользователе
    return jsonify({"id": user.id, 'email': user.email, "status" : "success" })

#Верифицируем пароль, введенный пользователем
@auth.verify_password
def verify_password(email, password):
    user = User.query.filter_by(email = email).first()
    if not user or not user.verify_password(password):
        return False
    g.user = user
    return True

# Рут для отправки списка тестов
@app.route('/api/tests')
@auth.login_required
def get_dashboard():
    user = User.query.filter_by(email = auth.username()).first()
    all_tests = [test_schema.dump(test) for test in Test.query.all()] #Получаем и сериализируем все тесты
    teacher_tests = [test_schema.dump(test) for test in user.tests.all()]#Получаем и сериализируем тесты, созданные данным пользователем
    #Если пользователь учитель, отправляем созданные им тесты
    if user.is_teacher:
        response = {
            "email": user.email,
            "isTeacher": True,
            "tests": teacher_tests,
            "isTeacher": 1
        } 
    #Если пользователь не учитель, отправляем все тесты
    else:
        response = {
            "email": user.email,
            "isTeacher": False,
            "tests": all_tests,
            "isTeacher": 0
        }
    return jsonify(response)

#Рут для создания теста
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

#Определяем максимально возможное количество баллов
def get_max_score(path):
    f = open(path, 'r')
    num_lines = sum(1 for line in open(path))
    return num_lines

#Дешифруем base64 код с фронтенда
def put_test_file(bin):
    s = string.ascii_lowercase+string.digits
    name = ''.join(random.sample(s,10))
    name+='.csv'
    path = os.path.dirname(os.path.abspath(__file__))
    new_file_path = os.path.join(path, name) # Создаем файл с рандомной строкой в качестве имени
    f = open(new_file_path, 'wb')
    f.write(bin)
    f.close()
    return new_file_path #Возвращаем путь к файлу

#Создаем json для обображения на фронтенде
def create_json(path):
    f = open(path, 'r')
    questions = []
    #Для каждой строки получаем список из элементов в каждом столбце
    for line in f.readlines():
        line = line.replace("\n", "")
        print(line)
        arr = line.split(';') 
        print(arr)
        quest = arr[0] #Определяем элемент с вопросом
        answers = []
        #Определяем элементы с ответам и ззаписываем правильные они или нет
        for i in range(1, 5):
            is_right = True if int(arr[5]) == i else False
            if arr[i]:
                answers.append({
                "answer" : arr[i],
                "isRight": is_right
            })
        img = arr[6] #Определяем элемент со ссылкой на картинку
        questions.append({
            "question" : quest,
            "answers": answers,
            "img": img
        })
    f.close()
    return {"questions": questions}


#Рут для отправки json с вопросами и ответами для отображения на фронтенде
@app.route('/api/tests/<int:test_id>')
@auth.login_required
def get_test(test_id):
    test = Test.query.filter_by(id=test_id).first()
    response = {"maxTime": test.max_time}
    response.update(create_json(test.path))
    return jsonify(response)

#Рут для обработки запросов, связанных с рельтатами
@app.route('/api/results', methods=["POST", "GET"])
@auth.login_required
def results():
    #Если метод POST, то записываем результат
    if request.method == 'POST':
        user = User.query.filter_by(email = auth.username()).first()
        test_id = request.json.get('testId')
        result = Result(score = request.json.get('score'))
        test = Test.query.filter_by(id=test_id).first()
        result.finished_test = test
        user.finished_tests.append(result)
        db.session.add(user)
        db.session.commit()
        return jsonify({"message": "success"})
    #Если метод GET, то отправляем запись о результатах на фронтенд
    else:
        teacher = User.query.filter_by(email = auth.username(), is_teacher=1).first()
        if teacher is None:
            return jsonify({"message": "Пользователь не является учителем"})
        
        results = [results_schema.dump(Result.query.filter_by(test_id=test.id)) for test in teacher.tests]
        response = {"results": results}
        return jsonify(response)


#Запускаем сервер
if __name__ == '__main__':
    app.run(debug=True)
