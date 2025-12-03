import streamlit_authenticator as stauth

# Crie um dicionário temporário com a senha
credentials = {'usernames': {'temp': {'password': 'minhasenha123'}}}

# Faça o hashing (modifica o dicionário in place)
stauth.Hasher.hash_passwords(credentials)

# Imprima o hash gerado
print(credentials['usernames']['temp']['password'])