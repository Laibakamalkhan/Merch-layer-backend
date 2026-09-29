class EncryptionProvider:
    def encrypt(self,value:bytes)->bytes: raise NotImplementedError
    def decrypt(self,value:bytes)->bytes: raise NotImplementedError
