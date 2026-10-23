"""Synthetic unmixing checks; these cannot prove preservation of real artwork."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

from PIL import Image, ImageDraw
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from clean_chroma import clean_frame, clean_directory, visible_key_count, rgba_pixels
from petlib import digest, write_json


class ChromaTests(unittest.TestCase):
    def fixture(self, foreground=(40,90,180)):
        image=Image.new('RGBA',(40,40))
        draw=ImageDraw.Draw(image)
        draw.rectangle((9,9,30,30),fill=tuple(round(.5*f+.5*k) for f,k in zip(foreground,(255,0,255)))+(255,))
        draw.rectangle((10,10,29,29),fill=foreground+(255,))
        return image

    def test_mixed_key_is_unmixed_without_geometry_changes(self):
        image=self.fixture()
        cleaned,report=clean_frame(image)
        self.assertGreater(visible_key_count(image),0)
        self.assertEqual(visible_key_count(cleaned),0)
        self.assertEqual(cleaned.size,image.size)
        self.assertEqual(cleaned.getchannel('A').getbbox(),image.getchannel('A').getbbox())
        for got,wanted in zip(cleaned.getpixel((9,15))[:3],(40,90,180)):
            self.assertLess(abs(got-wanted),4)
        self.assertTrue(125<=cleaned.getpixel((9,15))[3]<=131)

    def test_opaque_blue_white_skin_remain_identical(self):
        for color in ((40,90,180),(255,255,255),(245,178,160)):
            with self.subTest(color=color):
                image=self.fixture(color)
                cleaned,report=clean_frame(image)
                self.assertEqual(cleaned.getpixel((10,10)),color+(255,))
                self.assertEqual(cleaned.getpixel((20,20)),color+(255,))
                self.assertEqual(report['visible_key_after'],0)

    def test_neighbor_mode_preserves_sampled_lavender_and_geometry(self):
        color = (205, 200, 225)
        image = self.fixture(color)
        cleaned, report = clean_frame(image, rgb_mode='neighbor')
        self.assertEqual(cleaned.getpixel((9,15))[:3], color)
        self.assertEqual(cleaned.getpixel((20,20)), color+(255,))
        self.assertEqual(cleaned.getchannel('A').getbbox(), image.getchannel('A').getbbox())
        self.assertEqual(report['visible_key_after'], 0)
        self.assertFalse(any(g>r+10 and g>b+10 for r,g,b,a in rgba_pixels(cleaned) if a>16))

    def test_enclosed_interior_magenta_not_changed(self):
        image=self.fixture()
        image.putpixel((20,20),(220,20,210,255))
        cleaned,report=clean_frame(image)
        self.assertEqual(cleaned.getpixel((20,20)),image.getpixel((20,20)))
        self.assertEqual(report['interior_magenta_untouched'],1)

    def test_confirmed_interior_key_requires_explicit_opt_in(self):
        image=self.fixture()
        image.putpixel((20,20),(220,20,210,255))
        cleaned,report=clean_frame(image,rgb_mode='neighbor',include_interior_key=True)
        self.assertNotEqual(cleaned.getpixel((20,20)),image.getpixel((20,20)))
        self.assertEqual(report['interior_magenta_processed'],1)
        self.assertEqual(cleaned.getpixel((21,20)),image.getpixel((21,20)))

    def test_confirmed_cool_residue_in_warm_art_is_opt_in(self):
        image=self.fixture((190,90,40))
        image.putpixel((20,20),(49,29,139,132))
        default,_=clean_frame(image,rgb_mode='neighbor',include_interior_key=True)
        self.assertEqual(default.getpixel((20,20)),image.getpixel((20,20)))
        cleaned,report=clean_frame(image,rgb_mode='neighbor',include_interior_key=True,foreground_palette='warm')
        self.assertEqual(cleaned.getpixel((20,20))[:3],(190,90,40))
        self.assertEqual(cleaned.getpixel((21,20)),image.getpixel((21,20)))
        self.assertEqual(report['cool_residue_after'],0)

    def test_enclosed_transparent_hair_gap_is_cleaned(self):
        image=self.fixture()
        image.putpixel((20,20),(0,0,0,0))
        image.putpixel((20,19),(148,45,218,255))
        cleaned,report=clean_frame(image)
        self.assertNotEqual(cleaned.getpixel((20,19)),image.getpixel((20,19)))
        self.assertEqual(cleaned.getpixel((20,20)),(0,0,0,0))
        self.assertEqual(cleaned.getpixel((21,19)),image.getpixel((21,19)))

    def test_all_transparent_pixels_have_zero_rgb(self):
        image=self.fixture()
        image.putpixel((0,0),(255,0,255,0))
        cleaned,report=clean_frame(image)
        self.assertTrue(all(r==g==b==0 for r,g,b,a in rgba_pixels(cleaned) if a==0))
        self.assertEqual(report['normalized_transparent_pixels'],1)

    def test_frame_count_and_sources_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            source=root/'source'
            (source/'idle').mkdir(parents=True)
            files=[]
            for i in range(2):
                path=source/'idle'/f'{i:02}.png'
                self.fixture().save(path)
                files.append(path)
            hashes={str(p):digest(p) for p in files}
            write_json(source/'frames-manifest.json',{'chroma_key':{'rgb':[255,0,255]},'rows':[{'state':'idle','frames':[str(p) for p in files],'method':'stable-slots'}]})
            report=clean_directory(source,root/'candidate')
            self.assertEqual(report['frame_count_before'],2)
            self.assertEqual(report['frame_count_after'],2)
            self.assertEqual({str(p):digest(p) for p in files},hashes)
            manifest=json.loads((root/'candidate/frames-manifest.json').read_text())
            self.assertEqual(manifest['rows'][0]['method'],'stable-slots')
            self.assertTrue(all(Path(p).is_file() for p in manifest['rows'][0]['frames']))
            with self.assertRaisesRegex(ValueError,'never overwritten'):
                clean_directory(source,root/'candidate')

    def test_alpha_mode_and_band_bounds_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'RGBA'):
            clean_frame(Image.new('RGB',(40,40)))
        with self.assertRaisesRegex(ValueError,'band'):
            clean_frame(self.fixture(),band=100)


if __name__=='__main__':
    unittest.main()
