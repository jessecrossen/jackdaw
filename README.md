JACKDAW
=======
<img align="right" hspace="12" vspace="12"  src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/src/jackdaw/icons/logo_256.png"/>
JACKDAW is a Digital Audio Workstation (or DAW), based on the [JACK Audio Connection Kit](http://jackaudio.org/). It's essentially an intuitive graphical patchbay with a built-in MIDI sequencer, allowing you to connect MIDI instruments with tools like [LinuxSampler](http://www.linuxsampler.org/) and (coming soon) audio processing or soft-synth plugins based on [LADSPA](https://en.wikipedia.org/wiki/LADSPA), [DSSI](https://en.wikipedia.org/wiki/Disposable_Soft_Synth_Interface), or [LV2](https://en.wikipedia.org/wiki/LV2). All these tools are started, stopped, and managed by JACKDAW, so that you can save and restore your complete setup at any time. JACKDAW is written in [Python 2](https://www.python.org/), using [QT](http://qt-project.org/)'s [PySide bindings](http://qt-project.org/wiki/PySide) for the GUI and the [jackpatch module](https://github.com/jessecrossen/python-jackpatch) to interface with JACK. Right now, the application is in the alpha stage of development, so it isn't packaged with an installer or anything to make it easy to run, and the interface is still in flux so it isn't well documentation yet. Please check back in a few months if you're not a developer and just want to get it running and fool around.

INSTALLING
==========
If you have experience installing python modules, you should be able to get the application running by following these steps:
- Make sure JACK is installed on your system
- Make sure Python 2.7 is installed on your system
- Install [PySide](http://qt-project.org/wiki/PySide)
- Install [jackpatch](https://github.com/jessecrossen/python-jackpatch)
- Start the JACK server using something like [QJackCtl](http://qjackctl.sourceforge.net/) or the command line
- Clone this repository
- In a console, navigate to the source directory using `cd <clone location>/jackpatch/src`
- Run the application using `./app.py`

USING
=====
This is simple tutorial to cover the basics of using the application. When you start up, you should see an empty document like this:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/01-new-document.png"/>

Like the instructions say, left-clicking or right-clicking anywhere on the window will show you a menu of things to add to your workspace. These are called **units**, and form the basic elements of a document.

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/02-unit-menu.png"/>

Let's add a unit to get MIDI input from an instrument:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/03-inputs.png"/>

There's nothing inside the unit because no instruments have been plugged in (or possibly they have not been connected to JACK). At the top left of the unit you can see a grip that allows you to drag it around, and at the top right is an X button in case you want to delete it. Let's plug in a [QuNEXUS](http://www.keithmcmillen.com/products/qunexus/) and see what happens.

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/04-sampler.png"/>

As you can see, I've also added a sampled instrument by clicking on the workspace, selecting **Sampler Instrument...**, and choosing a file. The name is kind of long, but the neat thing is that almost any text you see in the interface can be edited to say whatever you want, and your edits will be remembered. I'm going to change it to just "tuba" for brevity:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/05-rename.png"/>

Okay, now we have an input and a synthesizer, but nothing is happening when we play. That's because they need to be connected together. The little stubs on the sides of the units are called **ports**, and they work kind of like the plug jacks on a physical piece of equipment. Ones on the left side of a unit are inputs, ones on the right are outputs. Diamond-shaped ones are MIDI ports, circular ones are audio ports. If there is one "wire" at the base of the port, it's mono, and if there are two it's stereo. To connect two ports, you just drag from one to the other:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/06-connecting.png"/>

If you want to disconnect, just grab the wire and drag on it to pull it out and then let go, just like you would with a physical patch cable. You can also click it and press delete on your keyboard, or right-click it and select Delete from the context menu. Okay, but there's still no sound! That's because the sampler isn't automatically connected to any outputs. This is because you might want to route its output through some effects or something like that. To connect it directly to the output, we can click on the workspace and add an **Audio Output** unit, then connect the port on the right side of the sampler to that:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/07-with-output.png"/>

Notice the doubled line indicating that the sampler output is in stereo. You can connect stereo and mono ports and JACKDAW will try to do the right thing, either mixing stereo down to mono or duplicating the mono channel onto each stereo channel. At any rate, we should now be able to hear some sound when we hit the keys. If not, make sure your volume is up and you're playing in an octave that the sampler instrument actually supports. Another important concept in JACKDAW is that it has hierarchical context menus. Notice how the tuba is inside the sampler unit, which is itself inside the workspace. If you right-click it, you'll see menu entries for each level of this hierarchy. That way you don't need to be that careful exactly where you right-click; as long as the mouse is inside an element, you should get a menu for it. For example, many elements can be given a color to make them stand out in complex documents. Here's the color menu for a unit:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/08-color-menu.png"/>
<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/09-colored.png"/>

So that's a basic setup for fooling around or playing live, but you can also record what you play, edit it, and play it back. To do all that, you'll need a **Sequencer** unit.

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/10-sequencer.png"/>

As you can see, we've connected the sequencer unit in between the MIDI instrument and the sampler. The sequencer has more controls than the other units. The main empty area of the unit is a track, which has its own inputs and outputs and works a lot like a track on a 4-track tape recorder (if you're old enough to have used those). The vertical red line is called the **transport** and is kind of like the tape head on a 4-track, marking a specific time where recording and playback will happen. On the bottom left is a + button which allows you to add more tracks (unlike the 4-track you get as many as you want!), and the bottom right has a grip that allows you to make the sequencer wider or narrower as needed. Below the track is a scrollbar that lets you navigate through time. The three buttons to the left of each track allow you to **aRm**, **Mute**, or **Solo** the track. Arming the track opens it up for recording. If the track isn't armed, nothing is going to be written onto it even if an instrument is connected. Muting a track stops it from playing, and soloing it stops *other* tracks from playing so you can hear it alone.

Okay, but at this point, you won't hear anything you play. That's because the track needs to be armed to preview what you're playing:

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/11-sequencer-armed.png"/>

Notice the background of the track changes to red, reminding you that it's ready for recording, and you should hear something when you play. This is a good time to practice what you're going to record. Click the big red circle on the toolbar to actually start recording. Click it again to stop. Now you should have a box with some notes in it, which is called a **block**, and is the basic container for a specific musical phrase.

<img src="https://raw.githubusercontent.com/jessecrossen/jackdaw/master/screenshots/basics/13-sequencer-data.png"/>

You can select and drag almost anything here: the block itself, the ends of the block, the notes. You can also use the arrow keys to move things around (hold shift to move in bigger jumps), and the delete or backspace keys to delete things. The musical repeat sign (two vertical lines with two dots to the left), can be used to control when the phrase repeats, as in the drum part above.

You might notice a couple things that are different from other DAWs here...
