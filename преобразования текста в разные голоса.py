import nltk
import numpy as np
import scipy
from bark.generation import (
    generate_text_semantic,
    preload_models,
)
from bark.api import semantic_to_waveform
from bark import generate_audio, SAMPLE_RATE

def text_to_audio(voice_preset='v2/ru_speaker_3'):

    text = """
    Философ, подбрасывая яблоко и говоря о том, что люди считают свои души подобными яблокам,
    задумался о том, насколько реально найти свою идеальную пару в мире, где столько людей.
    Он продемонстрировал, что мир жесток и перемалывает все под себя,     """.replace("\n", " ").strip()

    sentences = nltk.sent_tokenize(text)
    silence = np.zeros(int(0.25 * SAMPLE_RATE))

    pieces = []
    # for sentence in sentences:
    #     audio_array = generate_audio(sentence, history_prompt=voice_preset)
    #     pieces += [audio_array, silence.copy()]

    for sentence in sentences:
        semantic_tokens = generate_text_semantic(
            sentence,
            history_prompt=voice_preset,
            # temp=GEN_TEMP,
            min_eos_p=0.05,
        )
        audio_array = semantic_to_waveform(semantic_tokens, history_prompt=voice_preset)
        pieces += [audio_array, silence.copy()]

    scipy.io.wavfile.write(f'{voice_preset.split("/")[1]}_long.wav', rate=SAMPLE_RATE, data=np.concatenate(pieces))


def main():
    # preload_models()
    # text_to_audio()
    pass

if __name__ == '__main__':
    main()