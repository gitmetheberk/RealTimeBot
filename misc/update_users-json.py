import json
old_file = open("users_old.json", 'r')
old_json = json.load(old_file)

new_json = {}

for key in old_json.keys():
    user_dict = {}

    user_dict.update({"timezone" : old_json[key]})

    new_json.update({key : user_dict})

old_file.close()

new_file = open("users.json", 'w+')

json.dump(new_json, new_file)

new_file.close()