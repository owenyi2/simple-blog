---
title: Diffusion Example in PyTorch
date: 10/03/2026
---
Notebook: https://github.com/owenyi2/pytorch-diffusion-example/blob/main/main.ipynb

# Introduction

Synthetically generating images/video etc. is an exercise in sampling. In the set of all possible images, there is some region of images that we would recognise as images of cats for example. Generating images of cats amounts to drawing samples from a distribution concentrated on that region. 

We will not be generating images of cats. We will be doing a much easier task of sampling from 1D and 2D distributions but the idea will be the same.

Suppose we have 2D samples distributed like so

*Figure 1: Smile*
![|291](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538191752.webp)

The task is to generate points that could plausibly come from this distribution.
# Basic Idea

We take our samples and slowly add random noise to it. For notation suppose our original sample are realisations of some random variable $X_0$. The distribution $X_t = X_0 + W_t$ where $W_t$ is a Brownian motion so that $W_t \sim \mathcal{N}(0, \sigma^2t)$. 

*Figure 2: Adding noise*
![|500](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538216560.webp)

This gives us a sequence of distributions $X_t$ that look more and more like random noise. The final distribution is essentially pure noise and generating pure noise is very simple; just use `np.random.normal`.  

Now suppose we could teach the model to "denoise" our distribution. That is suppose we have a subroutine to generate samples from $X_{t}$, can we produce samples from $X_{t-\Delta t}$? 

In section 2.1 of this tutorial paper https://arxiv.org/pdf/2406.08929, they derive how generating samples of $X_{t - \Delta t}$ can be done by first sampling $X_t$ and then sampling a Gaussian with mean $\mathbb{E}[X_{t - \Delta t} \mid X_t]$. Therefore the task of denoising reduces to a regression problem where we try to learn the function $f(x) := \mathbb{E}[X_{t - \Delta t} \mid X_{t} = x]$. 

To see intuitively why this is something that should be achievable first consider the scenario of trying to sample $X_{t - \Delta t}$ from $X_t$ for large $t$ e.g. $t = 7$, $\Delta t = 2$, $\sigma = 1$. 

*Figure 3a: Behaviour we want model to learn (large t)*
![|291](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538266233.webp)

If you pass in a particular orange point into a model, it would be impossible to tell you from which exact point it came from. That's trying to take a realisation $x_t$ and predicting exactly what $x_{t - \Delta t}$ was or equivalently predicting exactly what number the Gaussian $W_t - W_{t - \Delta t} \sim \mathcal{N}(0, \Delta t)$ landed on. However, the model could learn that on an ensemble level, the original point was probably closer to the origin than further away. Learning $f(x) := \mathbb{E}[X_{t - \Delta t} \mid X_{t} = x]$ means recognising that to sample a blue point given an orange point, we should bias the orange point towards the origin. 

This biasing only reconstructs the mean location of $X_{t - \Delta t}$ given $X_t$. In the inference stage, we still need to add random noise back. More on this in [Inference](#Inference) section.

Next consider the scenario where $t$ is fairly small e.g. $t = 0.001$ and $\Delta t = 0.001$. This is where the model needs to learn subtle details. For certain regions of space, the model should learn that actually the conditional mean $\mathbb{E}[X_{t - \Delta t} \mid X_{t} = x]$ points outwards. Suppose that the original distribution had concentration around $(0.4, 0.7)$ (the left eye). Since $\Delta t$ is very small, there is not much displacement that diffusion could generate and so for points $X_t$ near the eye, it is more parsimonious for them to originate from the eye rather than elsewhere e.g. the face outline. 

The intuition to have is that there is some underlying time varying vector field which tells you how to shape a pure Gaussian noise into the distribution we desire and this is what we want the model to learn. For large times $t$, the vector field points mostly towards the mean of the distribution and for small times $t$, the vector field is more nuanced and points to closer by regions of concentration. 

*Figure 3b: Behaviour we want model to learn (small t)*
![|363](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538295727.webp)
# Pedagogical Example

I chose to train a separate model for each $t$ in a discrete set of times $t$. This way each model at time $t$ is a simple $\mathbb{R}^2 \to \mathbb{R}^2$ map and we can debug the model by plotting this map as a vector field. 

## Variance Reduction 

While we motivated diffusion by describing how to obtain $X_{t- \Delta t}$ from $X_t$, in practise we use a variance reduction method to simply learn $\mathbb{E}[X_0 \mid X_t]$. It turns out that 
$$\mathbb{E}[X_{t - \Delta t} - X_t \mid X_t] = \frac{\Delta t}{t} \mathbb{E}[X_0 - X_t \mid X_t]$$
Morally, the displacement $X_0 - X_t$ is $t / \Delta t$ times larger than the displacement $X_{t - \Delta t} - X_t$ and so we may grok why this may be true. You may protest that the quantities are dependent, both involving $X_t$ but the nice about expectations is that when we work with sums, Linearity of Expectation does not require independence. On page 12 of the tutorial paper https://arxiv.org/pdf/2406.08929 they describe this in more detail and in the appendix on page 45 they provide a formal proof. 

Even though in the exposition we described that we want to fit to $f(x) := \mathbb{E}[X_{t - \Delta t} \mid X_{t} = x]$, in the following sections we will instead be fitting to $g(x) := \mathbb{E}[X_0 - X_t \mid X_t = x]$. Using the variance reduction and linearity we can see that $g(x) = \frac{t}{\Delta t} (f(x) - x)$ so our model is learning the same thing, it just means during inference, we have to undo the transformations to recover $f(x)$. 
## Model

```python
class Model(nn.Module):
    def __init__(self):
        super().__init__()

        hidden_size = 256
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(2, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 2)
        )

    def forward(self, x):
        y = self.linear_relu_stack(x)
        return y
```

The model is a simple multilayer perceptron with ReLU activation functions. The input and output layer have 2 nodes since each model is a map $\mathbb{R}^2 \to \mathbb{R}^2$. 

## Creating Dataset and Training

```python
def train(model, inputs, outputs):
    criterion = nn.MSELoss()
    optimiser = optim.Adam(model.parameters(), lr = 0.001)
    num_epochs = 2000

    for epoch in range(num_epochs):
        model.train()
        optimiser.zero_grad()

        model_outputs = model(inputs)
        loss = criterion(model_outputs, outputs)

        loss.backward()
        optimiser.step()

        if (epoch + 1) % 100 == 0:
            print(f'Epoch [{epoch + 1}/{num_epochs}], Loss: {loss.item():.4f}')
    return model

models = []
ts = [0.0001, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.1, 0.2, 0.4, 0.6, 0.8, 1]

for t in ts:
    inputs = []
    outputs = []

    noise = rng.normal(0, np.sqrt(terminal_variance), smile.shape)
    noisy_smile = smile + np.sqrt(t) * noise 

    inputs = noisy_smile # x_t
    outputs = smile - noisy_smile

    tensor_inputs = torch.tensor(inputs, dtype = torch.float32, device = device)
    tensor_outputs = torch.tensor(outputs, dtype = torch.float32, device = device)
    
    model = Model().to(device)
    models.append(
        train(model, tensor_inputs, tensor_outputs)
    )
```

Because we are learning $g(x) := \mathbb{E}[X_0 - X_t \mid X_t = x]$, the input tensor is simply the noisy smile and the output tensor is the original smile minus the noisy smile. 

The original smile is an array with shape $(N, 2)$ so we generate noise of same shape. Therefore the input and output tensors are also $(N, 2)$.

## Visualising Models

The docs for [`matplotlib.axes.Axes.quiver`](https://matplotlib.org/stable/api/_as_gen/matplotlib.axes.Axes.quiver.html) read 

> Plot a 2D field of arrows.
> 
> Call signature:
> `quiver([X, Y], U, V, [C], /, **kwargs)`
> 
> X, Y define the arrow locations, U, V define the arrow directions, and C optionally sets the color. The arguments X, Y, U, V, C are positional-only.

We create a grid of input points `xy`. Our model already produces a displacement $X_0 - X_t$ given $X_t$. So we can pass the model outputs directly for `u` and `v`. To also plot the endpoints we can take `model(xy) + xy`. Of course we haven't normalised by $\frac{t}{\Delta t}$ but we don't really care about the magnitude, just the direction suffices for visualising. 

```python
def visualise_model_as_vector_field(
    model, x_start, x_end, y_start, y_end, grid_step, ax
):
    xy = np.mgrid[y_start:y_end:grid_step, y_start:y_end:grid_step].reshape(2, -1).T

    ax.scatter(xy[:, 0], xy[:, 1], 
                color='black', s=20, label='Original')

    # Model produces Displacements E[X_0 - X_t | X_t]
    uv = model(xy)

    u = uv[:, 0] 
    v = uv[:, 1] 

    ax.quiver(
        xy[:, 0],
        xy[:, 1],
        u,
        v,
        angles='xy',
        scale_units='xy',
        scale=1,
        color='blue'
    )

    # therefore to obtain the endpoints we take xy + uv
    ax.scatter(xy[:, 0] + uv[:, 0], xy[:, 1] + uv[:, 1], 
                color='red', s=15, label='Model output')

    ax.set_xlim(x_start, x_end)
    ax.set_ylim(y_start, y_end)
    ax.set_aspect('equal')
    ax.legend(loc='center left', bbox_to_anchor=(1.02, 0.5))
    ax.set_title("Vector Field: x → model(x)")

fig, ax = plt.subplots()

visualise_model_as_vector_field(
    lambda xy: models[0](
        torch.tensor(xy, dtype=torch.float32, device=device)
    ).cpu().detach().numpy(),
    0, 1, 0, 1, 0.04, ax
)
plt.show()

fig, ax = plt.subplots()

visualise_model_as_vector_field(
    lambda xy: models[-1](
        torch.tensor(xy, dtype=torch.float32, device=device)
    ).cpu().detach().numpy(),
    -1, 1, -1, 1, 0.09, ax
)
plt.show()
```

Plotting the model for the smallest and largest $t$ gives

*Figure 4a and 4b: Vector Field of t = 0.0001 and t = 1 model*
![|300](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538364744.webp)![|310](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538381038.webp)
We can see that the fine details of the outline and smile are learnt for the $t = 0.0001$ model and the general fact that our smile is centred at $(0.5, 0.5)$ rather than $(0, 0)$ is picked up on by the $t = 1$ model. 

## Inference

```python
inference_ts = list(reversed(ts)) + [0]

n_samples = 1000
sample = torch.tensor(rng.normal(0, np.sqrt(terminal_variance), (n_samples, 2)), dtype = torch.float32, device = device, requires_grad = False)

for i in range(len(ts)):
    delta_t = inference_ts[i] - inference_ts[i+1]
    t = inference_ts[i]
    model = models[-(i+1)]

    with torch.inference_mode():
        sample = sample + model(sample) * delta_t / t 
        sample += torch.tensor(
            rng.normal(0, np.sqrt(terminal_variance * delta_t), (n_samples, 2)), dtype = torch.float32, device = device
        )

sample = sample.cpu().detach().numpy()

sample[(0 < sample[:, 0]) & (sample[:, 0] < 1) & (0 < sample[:, 1]) & (sample[:, 1] < 1)] # a little bit of rejection sampling post-processing
plt.scatter(
    sample[:, 0], sample[:, 1], label = "denovo smile generated by model"
)
plt.scatter(
    smile[:, 0], smile[:, 1], alpha = 0.08, label = "original dataset"
)
plt.legend(loc = "best")
plt.show()
```

For each step between two consecutive `t` in `ts`, we compute the $\Delta t$ in order to obtain the correct scale factor $\Delta t/ t$ in order to undo the variance reduction trick. 

Observe that `sample = sample + model(sample) * delta_t / t`. This essentially undoes $g(x) = \frac{t}{\Delta t} (f(x) - x)$ so this line is as if we trained `f` and did `sample = f(sample)`. Recall $f(x) := \mathbb{E}[X_{t - \Delta t} \mid X_t = x]$. 

Now we said in [Basic Idea](#Basic%20Idea) that for the forward pass it is not enough to perform the biasing `sample = f(sample)` and that we still need to add random noise. This is because the inductive idea of the procedure is given a sampler for $X_t$ can we get a sampler for $X_{t - \Delta t}$. For a given $X_t = x$, the conditional expectation $\mathbb{E}[X_{t - \Delta t} | X_t = x]$ is just a fixed number and not a distribution. Instead, it is the mean of the distribution that we want which we are told is approximately normal with variance $\sigma^2 \Delta t$. Therefore in each step we also do `sample += normal(0, terminal_variance * delta_t)`.

*Figure 5: Result*
![|300](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538432190.webp)
# Combining into a Single Model

Training a separate model for each $t$ is not ideal. One limitation is that you are locked in to your discretisation scheme during inference. Our `ts` were `[1.0, 0.8, 0.6, ...]` and so we can't use a smaller $\Delta t$ to reduce discretisation error during inference. Apart from that, it's just not very elegant having a separate model for each choice of $t$. 

If we train a single model $\mathbb{R}^2 \times [0, 1] \to \mathbb{R}^2$ which takes in the time parameter $t \in [0, 1]$, then we can choose whatever discretisation scheme we want during inference. 

## Model

```python
class UnifiedModel(nn.Module):
    def __init__(self):
        super().__init__()

        hidden_size = 512
        self.linear_relu_stack = nn.Sequential(
            nn.Linear(2 + 1, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, 2)
        )

    def forward(self, x):
        y = self.linear_relu_stack(x)
        return y

model = UnifiedModel().to(device)

```

Notice the input dimension is now 3. Also notice the `hidden_size` is 512 compared to before being 256. We are tasking our model with memorising a lot more information so adding more parameters would be helpful. 

## Creating Dataset and Training

The first thing I tried was just concatenate the training examples from before and feeding it into the training loop. The results were subpar to say the least.

The reason why is because if you have a look at Figure 2 again, you see that most of the fine grained details disappeared between the first two frames and that from frame 3 onwards, the observation is mostly the same which is things diffuse outwards. 

So essentially we really want to emphasise to our model the importance of getting cases for small $t$ correct. One approach is to just provide a lot more training examples for small $t$ and less examples on large $t$. 

We created a noise schedule and produced sample as follows. I obtained this function by tweaking around plots on Desmos to get a curve that increases very slowly and remains below $0.025$ for a large amount of the domain $[0, 1]$ before rapidly increasing towards $1$ at the end and this seemed to produce decent results. 

Then by uniformly sampling $t \sim U(0, 1)$ and passing $k = \verb|noise_schedule|(t)$, we effectively overweight training examples involving small amounts of noise. For example $k < 0.025$ occurs about a third of the time. (This is essentially Inverse Transform Sampling. We effectively made $k$ follow a Power Law Distribution). 

There is one difference that using a noise schedule has compared to just oversampling small $t$. Observe that we still pass in $t$ through the input tensors which means the model sees the uniform $t$ rather than the actual noise amount $k$. This will again be important for the inference step. 

```python
# previously our ts were
# 0.0001, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.1, 0.2, 0.4, 0.6, 0.8, 1

def noise_schedule(t: float) -> float:
    """
    $t \in [0, 1]$
    
    We want for small $t$ e.g. $t < 0.5$, the noise to be very small e.g. < 0.025
    """
    a = 0.05
    c = 1 + a/(a+1)

    return a / (c - t) - a / c

plt.scatter(
    np.linspace(0, 1),
    noise_schedule(np.linspace(0, 1))
)
plt.show()

num_times = 100
smile = make_smile(200, 15, 50)

# plt.scatter(smile[:, 0], smile[: , 1])
inputs = []
outputs = []
for _ in range(num_times):
    t = rng.uniform(0, 1)
    k = noise_schedule(t)

    noise = rng.normal(0, np.sqrt(terminal_variance), smile.shape)
    noisy_smile = smile + np.sqrt(k) * noise

    inputs.append(
        np.hstack((
            noisy_smile, 
            t * np.ones((noisy_smile.shape[0], 1))
                   ))
    )
    outputs.append(
        smile - noisy_smile
    )
inputs = np.concatenate(inputs)
outputs = np.concatenate(outputs)

tensor_inputs = torch.tensor(inputs, dtype = torch.float32, device = device)
tensor_outputs = torch.tensor(outputs, dtype = torch.float32, device = device)
```

*Figure 6: Noise schedule*
![|250](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538456623.webp)

The training loop is same as before. 
## Visualising the Model

We can use the same quiver plot to visualise our model. By currying a particular $t$ into our model, we can get a vector field $\mathbb{R}^2 \to \mathbb{R}^2$ to plot. 

*Figure 7a and 7b: Vector field for a t = 0 and t = 0.8 model*
![|300](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538482932.webp)![|310](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538473817.webp)
## Inference

Recall that the amount of noise added is `k = noise_schedule(t)` but the parameter we pass in to the model is still `t`. In each step, we compute $t$ and $t - \Delta t$ and convert these into $k$ and $k - \Delta k$. In each step we pass in $t$ as usual into the model however we scale by $\frac{\Delta k}{k}$ to account for the variance reduction and we sample noise from $\mathcal{N}(0, \sigma^2 \Delta k)$. 

```python
ts = np.linspace(1, 0, 100)

inputs = rng.normal(0, np.sqrt(terminal_variance), (n_samples, 2))
sample = torch.tensor(inputs, dtype = torch.float32, device = device, requires_grad = False)

for i in range(len(ts) - 1):
    t = ts[i]
    t_next = ts[i+1]

    k = noise_schedule(t)
    delta_k = noise_schedule(t) - noise_schedule(t_next)

    with torch.inference_mode():
        sample = sample + model(
            torch.hstack((sample, t * torch.ones((sample.shape[0], 1), device=device))) 
            ) * delta_k / k
        time = t * np.ones((inputs.shape[0], 1))
        sample += torch.tensor(
            rng.normal(0, np.sqrt(terminal_variance * delta_k), (n_samples, 2)), dtype = torch.float32, device = device
        )

sample = sample.cpu().detach().numpy()
fig, ax = plt.subplots()
ax.scatter(
    sample[:, 0], sample[:, 1], label = "denovo smile generated by model"
)
ax.scatter(
    smile[:, 0], smile[:, 1], alpha = 0.08, label = "original dataset"
)
ax.legend(loc = "best")
ax.set_aspect("equal")

box = ax.get_position()
ax.set_position([box.x0, box.y0 + box.height * 0.1,
                 box.width, box.height * 0.9])

# Put a legend below current axis
ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05),
          fancybox=True, shadow=True, ncol=5)

plt.show()
```

*Figure 8: Result*
![|350](./Attachments/Diffusion%20Example%20in%20PyTorch-1773538525951.webp)

# Resources I Found Helpful

- https://jakiw.com/diffusion_model_intro
- https://arxiv.org/pdf/2406.08929
- https://www.youtube.com/watch?v=iv-5mZ_9CPY

