import streamlit_authenticator as stauth

# Hash'lenecek şifrelerinizi bu listeye yazın
passwords_to_hash = ['Uniq2025.'] 

# Bu sürüm için doğru kullanım:
# 1. Parola listesini Hasher'a verin
# 2. .generate() metodunu çağırın
hashed_passwords = stauth.Hasher(passwords_to_hash).generate()

print(hashed_passwords)