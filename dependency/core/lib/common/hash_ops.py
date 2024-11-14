
class HashOps:
    @staticmethod
    def get_frame_hash(frame):
        import imagehash
        from PIL import Image

        pil_img = Image.fromarray(frame)
        return imagehash.phash(pil_img)
