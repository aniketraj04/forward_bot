text = "123456, 67890"
channel_id1, channel_id2 = text.split(",")

x = text.split(",")


#print(str(x))

y = ""

for i in x:
    y = y+ i+ ","

print(y)
